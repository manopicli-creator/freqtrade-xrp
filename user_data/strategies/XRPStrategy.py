from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame
import talib.abstract as ta

class XRPStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '15m'
    stoploss = -0.05
    minimal_roi = {
        "0": 0.04,
        "120": 0.02,
        "240": 0.01,
        "480": 0
    }
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True
    use_exit_signal = False

    buy_rsi_min = IntParameter(30, 50, default=38, space='buy')
    buy_rsi_max = IntParameter(50, 70, default=62, space='buy')

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        return [(pair, '5m') for pair in pairs]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['ema200_1h'] = ta.EMA(dataframe, timeperiod=800)

        inf = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='5m')

        inf['rsi'] = ta.RSI(inf, timeperiod=14)
        inf['ema20'] = ta.EMA(inf, timeperiod=20)
        inf['ema50'] = ta.EMA(inf, timeperiod=50)

        macd = ta.MACD(inf, fastperiod=12, slowperiod=26, signalperiod=9)
        inf['macd'] = macd['macd']
        inf['macdsignal'] = macd['macdsignal']

        bollinger = ta.BBANDS(inf, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        inf['bb_upper'] = bollinger['upperband']

        inf['macd_cross_up'] = (
            (inf['macd'] > inf['macdsignal']) &
            (inf['macd'].shift(1) <= inf['macdsignal'].shift(1))
        )
        inf['volume_ok'] = inf['volume'] > inf['volume'].rolling(20).mean()

        inf.rename(columns={
            'rsi': '5m_rsi',
            'ema20': '5m_ema20',
            'ema50': '5m_ema50',
            'macd_cross_up': '5m_macd_cross_up',
            'bb_upper': '5m_bb_upper',
            'volume_ok': '5m_volume_ok'
        }, inplace=True)

        inf_15 = inf[['date', '5m_rsi', '5m_ema20', '5m_ema50',
                       '5m_macd_cross_up', '5m_bb_upper', '5m_volume_ok']].copy()
        inf_15['date'] = inf_15['date'].dt.floor('15min')
        inf_15 = inf_15.groupby('date').last().reset_index()

        dataframe = dataframe.merge(inf_15, on='date', how='left')
        dataframe.ffill(inplace=True)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['ema200_1h']) &
                (dataframe['close'] > dataframe['ema200']) &
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
