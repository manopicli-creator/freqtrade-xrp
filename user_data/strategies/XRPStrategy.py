from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame
import talib.abstract as ta

class XRPStrategy(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = '5m'

    stoploss = -0.08
    minimal_roi = {"0": 0.02, "60": 0.01, "120": 0.005, "240": 0}
    trailing_stop = False

    buy_rsi_min = IntParameter(30, 60, default=57, space='buy')
    buy_rsi_max = IntParameter(55, 75, default=58, space='buy')
    sell_rsi = IntParameter(60, 85, default=84, space='sell')

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['ema20'] = ta.EMA(dataframe, timeperiod=20)
        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=50)
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi'] > self.buy_rsi_min.value) &
                (dataframe['rsi'] < self.buy_rsi_max.value) &
                (dataframe['ema20'] > dataframe['ema50']) &
                (dataframe['macd'] > dataframe['macdsignal'])
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, 'exit_long'] = 0
        return dataframe