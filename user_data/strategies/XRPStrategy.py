from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from pandas import DataFrame
import talib.abstract as ta

class XRPStrategy(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = '5m'

    stoploss = -0.03
    minimal_roi = {
        "0": 0.02,
        "30": 0.01,
        "60": 0.005,
        "120": 0
    }

    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.015
    trailing_only_offset_is_reached = True

    # Paramètres optimisables
    buy_rsi_min = IntParameter(30, 55, default=40, space='buy')
    buy_rsi_max = IntParameter(50, 70, default=60, space='buy')
    sell_rsi = IntParameter(60, 85, default=70, space='sell')
    buy_bb_lower = DecimalParameter(0.95, 1.0, default=0.99, space='buy')

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # EMA
        dataframe['ema9'] = ta.EMA(dataframe, timeperiod=9)
        dataframe['ema21'] = ta.EMA(dataframe, timeperiod=21)
        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=50)

        # MACD
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        # Bollinger Bands
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_mid'] = bollinger['middleband']
        dataframe['bb_lower'] = bollinger['lowerband']

        # Volume moyen
        dataframe['volume_mean'] = dataframe['volume'].rolling(20).mean()

        # Stochastic RSI
        dataframe['fastk'], dataframe['fastd'] = ta.STOCHRSI(
            dataframe, timeperiod=14, fastk_period=3, fastd_period=3
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # RSI en zone neutre-haussière
                (dataframe['rsi'] > self.buy_rsi_min.value) &
                (dataframe['rsi'] < self.buy_rsi_max.value) &

                # Tendance haussière : EMA9 > EMA21 > EMA50
                (dataframe['ema9'] > dataframe['ema21']) &
                (dataframe['ema21'] > dataframe['ema50']) &

                # MACD haussier
                (dataframe['macd'] > dataframe['macdsignal']) &
                (dataframe['macdhist'] > 0) &

                # Prix proche ou sous la BB mid (bon point d'entrée)
                (dataframe['close'] < dataframe['bb_mid'] * self.buy_bb_lower.value) &

                # Volume au dessus de la moyenne (confirmation)
                (dataframe['volume'] > dataframe['volume_mean'] * 0.8) &

                # Stoch RSI pas encore suracheté
                (dataframe['fastk'] < 80)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # RSI suracheté
                (dataframe['rsi'] > self.sell_rsi.value) |

                # MACD croisement baissier
                (
                    (dataframe['macd'] < dataframe['macdsignal']) &
                    (dataframe['macdhist'] < 0)
                ) |

                # Prix au dessus de la BB upper (surachat)
                (dataframe['close'] > dataframe['bb_upper'])
            ),
            'exit_long'] = 1
        return dataframe
