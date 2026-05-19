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

    use_exit_signal = False  # Laisser ROI et trailing stop gérer les sorties

    buy_rsi_min = IntParameter(30, 50, default=38, space='buy')
    buy_rsi_max = IntParameter(50, 70, default=62, space='buy')

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['ema20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)

        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']

        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_mid'] = bollinger['middleband']

        # Croisement MACD haussier
        dataframe['macd_cross_up'] = (
            (dataframe['macd'] > dataframe['macdsignal']) &
            (dataframe['macd'].shift(1) <= dataframe['macdsignal'].shift(1))
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi'] > self.buy_rsi_min.value) &
                (dataframe['rsi'] < self.buy_rsi_max.value) &
                (dataframe['ema20'] > dataframe['ema50']) &
                (dataframe['close'] > dataframe['ema200']) &
                (dataframe['macd_cross_up'] == True) &
                (dataframe['close'] < dataframe['bb_upper']) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'exit_long'] = 0
        return dataframe
