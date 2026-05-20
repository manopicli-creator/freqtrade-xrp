from freqtrade.strategy import IStrategy, IntParameter, informative
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

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
        # Déclare les paires/timeframes supplémentaires à télécharger
        pairs = self.dp.current_whitelist()
        return [(pair, '5m') for pair in pairs]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- Indicateurs 15m (macro) ---
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['ema200_1h'] = ta.EMA(dataframe, timeperiod=800)

        # --- Données 5m (signaux d'entrée) ---
        inf_tf = '5m'
        informative = self.dp.get_pair_dataframe(
            pair=metadata['pair'],
            timeframe=inf_tf
        )

        # Calcul des indicateurs sur 5m
        informative['rsi'] = ta.RSI(informative, timeperiod=14)
        informative['ema20'] = ta.EMA(informative, timeperiod=20)
        informative['ema50'] = ta.EMA(informative, timeperiod=50)

        macd = ta.MACD(informative, fastperiod=12, slowperiod=26, signalperiod=9)
        informative['macd'] = macd['macd']
        informative['macdsignal'] = macd['macdsignal']

        bollinger = ta.BBANDS(informative, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        informative['bb_upper'] = bollinger['upperband']

        informative['macd_cross_up'] = (
            (informative['macd'] > informative['macdsignal']) &
            (informative['macd'].shift(1) <= informative['macdsignal'].shift(1))
        )
        informative['volume_ok'] = (
            informative['volume'] > informative['volume'].rolling(20).mean()
        )

        # Merge les données 5m dans le dataframe 15m
        dataframe = qtpylib.resample_to_interval(dataframe, 5)
        informative.columns = [f'5m_{c}' if c != 'date' else c for c in informative.columns]
        dataframe = dataframe.merge(
            informative[['date', '5m_rsi', '5m_ema20', '5m_ema50',
                         '5m_macd_cross_up', '5m_bb_upper', '5m_volume_ok']],
            on='date', how='left'
        ).ffill()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # Filtre macro 15m
                (dataframe['close'] > dataframe['ema200_1h']) &
                (dataframe['close'] > dataframe['ema200']) &
                # Signaux d'entrée 5m
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
        
