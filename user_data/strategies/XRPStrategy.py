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
        # --- Indicateurs macro 15m ---
        dataframe['ema200'] = ta.EMA(dataframe, timeperiod=200)
        dataframe['ema200_1h'] = ta.EMA(dataframe, timeperiod=800)

        # --- Données 5m ---
        inf = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='5m')

        inf['rsi'] = ta.RSI(inf, timeperiod=14)
        inf['ema20'] = ta.EMA(inf, timeperiod=20)
        inf['ema50'] = ta.EMA(inf, timeperiod=50)

        macd = ta.MACD(inf, fastperi
