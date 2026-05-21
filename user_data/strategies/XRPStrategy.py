from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame
import talib.abstract as ta

class XRPStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '15m'
    startup_candle_count = 800

    stoploss = -0.03
    minimal_roi = {
        "0": 0.03,
        "60": 0.02,
        "120": 0.01,
        "240": 0
    }

    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    use_exit_signal = False
    can_short = False

    buy_rsi_min = IntParameter(30, 50, default=38, space='buy')
    buy_rsi_max = IntParameter(50, 70, default=62, space='buy')

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative = [(pair, '5m') for pair in pairs]
        informative += [(pair, '1h') for pair in pairs]
        return informative

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- Indicateurs 15m ---
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['ema200_1h'] = ta.EMA(dataframe, timeperiod=800)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

        # --- Indicateurs 5m ---
        inf5 = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='5m')
        inf5['rsi'] = ta.RSI(inf5, timeperiod=14)
        inf5['ema20'] = ta.EMA(inf5, timeperiod=20)
        inf5['ema50'] = ta.EMA(inf5, timeperiod=50)
        macd = ta.MACD(inf5, fastperiod=12, slowperiod=26, signalperiod=9)
        inf5['macd'] = macd['macd']
        inf5['macdsignal'] = macd['macdsignal']
        bollinger = ta.BBANDS(inf5, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        inf5['bb_upper'] = bollinger['upperband']
        inf5['macd_cross_up'] = (
            (inf5['macd'] > inf5['macdsignal']) &
            (inf5['macd'].shift(1) <= inf5['macdsignal'].shift(1))
        )
        inf5['volume_ok'] = inf5['volume'] > inf5['volume'].rolling(20).mean()

        inf5.rename(columns={
            'rsi': '5m_rsi',
            'ema20': '5m_ema20',
            'ema50': '5m_ema50',
            'macd_cross_up': '5m_macd_cross_up',
            'bb_upper': '5m_bb_upper',
            'volume_ok': '5m_volume_ok'
        }, inplace=True)

        inf5_15 = inf5[['date', '5m_rsi', '5m_ema20', '5m_ema50',
                         '5m_macd_cross_up', '5m_bb_upper', '5m_volume_ok']].copy()
        inf5_15['date'] = inf5_15['date'].dt.floor('15min')
        inf5_15 = inf5_15.groupby('date').last().reset_index()
        dataframe = dataframe.merge(inf5_15, on='date', how='left')

        # --- Indicateurs 1h ---
        inf1h = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1h')
        inf1h['ema20_1h'] = ta.EMA(inf1h, timeperiod=20)
        inf1h['ema50_1h'] = ta.EMA(inf1h, timeperiod=50)
        inf1h['rsi_1h'] = ta.RSI(inf1h, timeperiod=14)

        inf1h_15 = inf1h[['date', 'ema20_1h', 'ema50_1h', 'rsi_1h']].copy()
        inf1h_15['date'] = inf1h_15['date'].dt.floor('15min')
        dataframe = dataframe.merge(inf1h_15, on='date', how='left')

        dataframe.ffill(inplace=True)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # Filtre macro
                (dataframe['ema200_1h'].notna()) &
                (dataframe['close'] > dataframe['ema200_1h']) &
                (dataframe['close'] > dataframe['ema200']) &
                # Tendance 1h haussière
                (dataframe['ema20_1h'] > dataframe['ema50_1h']) &
                (dataframe['close'] > dataframe['ema20_1h']) &
                (dataframe['rsi_1h'] > 45) &
                # Momentum 15m
                (dataframe['adx'] > 25) &
                (dataframe['close'].pct_change(4) > 0) &
                # Signaux 5m
                (dataframe['5m_ema20'] > dataframe['5m_ema50']) &
                (dataframe['5m_rsi'] > self.buy_rsi_min.value) &
                (dataframe['5m_rsi'] < self.buy_rsi_max.value) &
                (dataframe['5m_macd_cross_up'] == True) &
                (dataframe['close'] < dataframe['5m_bb_upper']) &
                (dataframe['5m_volume_ok']) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'exit_long'] = 0
        return dataframe
