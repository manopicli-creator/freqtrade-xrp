from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame
from datetime import datetime, timezone
from typing import Optional
import talib.abstract as ta
import pandas as pd

class XRPStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '15m'
    startup_candle_count = 200  # réduit de 800 → démarrage plus rapide

    # --- Stoploss dur ---
    stoploss = -0.04
from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame
from datetime import datetime
from typing import Optional
import talib.abstract as ta
import pandas as pd

class XRPStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '15m'
    startup_candle_count = 200

    stoploss = -0.03  # stoploss dur de sécurité absolue

    # Trailing stop : laisse courir les gains
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # custom_stoploss activé
    use_custom_stoploss = True

    minimal_roi = {
        "0": 0.10,
        "480": 0.05,
        "960": 0.02,
        "1440": 0
    }

    use_exit_signal = True
    exit_profit_only = False
    can_short = False

    buy_rsi_min = IntParameter(30, 50, default=35, space='buy')
    buy_rsi_max = IntParameter(50, 70, default=65, space='buy')
    buy_adx_min = IntParameter(10, 30, default=10, space='buy')

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative = [(pair, '5m') for pair in pairs]
        informative += [(pair, '1h') for pair in pairs]
        return informative

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

        # Indicateurs 5m
        inf5 = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='5m')
        inf5['rsi'] = ta.RSI(inf5, timeperiod=14)
        inf5['ema20'] = ta.EMA(inf5, timeperiod=20)
        inf5['ema50'] = ta.EMA(inf5, timeperiod=50)
        inf5['volume_ok'] = inf5['volume'] > inf5['volume'].rolling(20).mean()

        inf5.rename(columns={
            'rsi': '5m_rsi',
            'ema20': '5m_ema20',
            'ema50': '5m_ema50',
            'volume_ok': '5m_volume_ok'
        }, inplace=True)

        inf5_15 = inf5[['date', '5m_rsi', '5m_ema20', '5m_ema50', '5m_volume_ok']].copy()
        inf5_15['date'] = inf5_15['date'].dt.floor('15min')
        inf5_15 = inf5_15.groupby('date').last().reset_index()
        dataframe = dataframe.merge(inf5_15, on='date', how='left')

        # Indicateurs 1h
        inf1h = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1h')
        if len(inf1h) > 0:
            inf1h['ema20_1h'] = ta.EMA(inf1h, timeperiod=20)
            inf1h['ema50_1h'] = ta.EMA(inf1h, timeperiod=50)
            inf1h['rsi_1h'] = ta.RSI(inf1h, timeperiod=14)
            inf1h['date'] = pd.to_datetime(inf1h['date'])
            inf1h_15 = inf1h[['date', 'ema20_1h', 'ema50_1h', 'rsi_1h']].copy()
            inf1h_15['date'] = inf1h_15['date'].dt.floor('15min')
            dataframe = dataframe.merge(inf1h_15, on='date', how='left')
        else:
            dataframe['ema20_1h'] = float('nan')
            dataframe['ema50_1h'] = float('nan')
            dataframe['rsi_1h'] = float('nan')

        # Score de force du signal (utilisé par custom_stake_amount)
        dataframe['signal_score'] = 0
        dataframe.loc[dataframe['adx'] > 20, 'signal_score'] += 1
        dataframe.loc[dataframe['adx'] > 30, 'signal_score'] += 1
        dataframe.loc[
            (dataframe['5m_rsi'] > 45) & (dataframe['5m_rsi'] < 60),
            'signal_score'
        ] += 1
        dataframe.loc[
            dataframe['5m_ema20'] > dataframe['5m_ema50'],
            'signal_score'
        ] += 1

        dataframe.ffill(inplace=True)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['adx'] > self.buy_adx_min.value) &
                (dataframe['5m_ema20'] > dataframe['5m_ema50']) &
                (dataframe['5m_rsi'] > self.buy_rsi_min.value) &
                (dataframe['5m_rsi'] < self.buy_rsi_max.value) &
                (dataframe['5m_volume_ok']) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi_1h'] < 40) &
                (dataframe['ema20_1h'] < dataframe['ema50_1h'])
            ),
            'exit_long'] = 1
        return dataframe

    def custom_stoploss(self, pair: str, trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> Optional[float]:
        """
        Stoploss progressif selon la durée du trade :
        - Avant 1h  : stoploss dur à -3% (laisse respirer)
        - Après 1h  : stoploss à -3%
        - Après 2h  : stoploss à -2%
        - Après 3h  : stoploss à -1%
        Si le trade est positif, on laisse le trailing stop gérer.
        """
        hours = (current_time - trade.open_date_utc).total_seconds() / 3600

        # Ne pas court-circuiter le trailing stop si on est en profit
        if current_profit > 0.02:
            return None  # laisse le trailing gérer

        if hours >= 3:
            return -0.01   # après 3h : -1%
        elif hours >= 2:
            return -0.02   # après 2h : -2%
        elif hours >= 1:
            return -0.03   # après 1h : -3%

        return None  # avant 1h : stoploss dur par défaut (-3% défini en haut)

    def custom_stake_amount(self, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        """
        Stake dynamique selon la force du signal :
        - Signal faible (score 0-1) : 15% du capital dispo
        - Signal moyen (score 2-3)  : 25% du capital dispo
        - Signal fort  (score 4)    : 35% du capital dispo
        """
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(
                kwargs.get('pair', ''), self.timeframe
            )
            if len(dataframe) == 0:
                return proposed_stake * 0.20

            score = int(dataframe.iloc[-1]['signal_score'])
        except Exception:
            score = 0

        available = self.wallets.get_available_capital()

        if score >= 4:
            pct = 0.35
        elif score >= 2:
            pct = 0.25
        else:
            pct = 0.15

        stake = available * pct

        # Respecte les limites min/max
        if min_stake and stake < min_stake:
            stake = min_stake
        if stake > max_stake:
            stake = max_stake

        return stake

    def custom_exit(self, pair: str, trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        # Garde uniquement la sortie d'urgence à 8h (le custom_stoploss gère le reste)
        hours = (current_time - trade.open_date_utc).total_seconds() / 3600
        if hours >= 8 and current_profit < 0:
            return "exit_8h_negative"
        return None
    # --- Trailing stop : laisse courir les gains ---
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # --- ROI minimal : on laisse le trailing gérer la sortie ---
    minimal_roi = {
        "0": 0.10,
        "480": 0.05,
        "960": 0.02,
        "1440": 0
    }

    use_exit_signal = True
    exit_profit_only = False
    can_short = False

    # --- Paramètres hyperopt ---
    buy_rsi_min = IntParameter(30, 50, default=35, space='buy')
    buy_rsi_max = IntParameter(50, 70, default=65, space='buy')
    buy_adx_min = IntParameter(10, 30, default=10, space='buy')

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative = [(pair, '5m') for pair in pairs]
        informative += [(pair, '1h') for pair in pairs]
        return informative

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

        # --- Indicateurs 5m ---
        inf5 = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='5m')
        inf5['rsi'] = ta.RSI(inf5, timeperiod=14)
        inf5['ema20'] = ta.EMA(inf5, timeperiod=20)
        inf5['ema50'] = ta.EMA(inf5, timeperiod=50)
        inf5['volume_ok'] = inf5['volume'] > inf5['volume'].rolling(20).mean()

        inf5.rename(columns={
            'rsi': '5m_rsi',
            'ema20': '5m_ema20',
            'ema50': '5m_ema50',
            'volume_ok': '5m_volume_ok'
        }, inplace=True)

        inf5_15 = inf5[['date', '5m_rsi', '5m_ema20', '5m_ema50', '5m_volume_ok']].copy()
        inf5_15['date'] = inf5_15['date'].dt.floor('15min')
        inf5_15 = inf5_15.groupby('date').last().reset_index()
        dataframe = dataframe.merge(inf5_15, on='date', how='left')

        # --- Indicateurs 1h ---
        inf1h = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1h')
        if len(inf1h) > 0:
            inf1h['ema20_1h'] = ta.EMA(inf1h, timeperiod=20)
            inf1h['ema50_1h'] = ta.EMA(inf1h, timeperiod=50)
            inf1h['rsi_1h'] = ta.RSI(inf1h, timeperiod=14)
            inf1h['date'] = pd.to_datetime(inf1h['date'])
            inf1h_15 = inf1h[['date', 'ema20_1h', 'ema50_1h', 'rsi_1h']].copy()
            inf1h_15['date'] = inf1h_15['date'].dt.floor('15min')
            dataframe = dataframe.merge(inf1h_15, on='date', how='left')
        else:
            dataframe['ema20_1h'] = float('nan')
            dataframe['ema50_1h'] = float('nan')
            dataframe['rsi_1h'] = float('nan')

        dataframe.ffill(inplace=True)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['adx'] > self.buy_adx_min.value) &
                (dataframe['5m_ema20'] > dataframe['5m_ema50']) &
                (dataframe['5m_rsi'] > self.buy_rsi_min.value) &
                (dataframe['5m_rsi'] < self.buy_rsi_max.value) &
                (dataframe['5m_volume_ok']) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Sortie sur retournement de tendance 1h
        dataframe.loc[
            (
                (dataframe['rsi_1h'] < 40) &
                (dataframe['ema20_1h'] < dataframe['ema50_1h'])
            ),
            'exit_long'] = 1
        return dataframe

    def custom_exit(self, pair: str, trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        trade_duration_hours = (current_time - trade.open_date_utc).total_seconds() / 3600

        # Après 4h en négatif > -1% : sortie forcée
        if trade_duration_hours >= 4 and current_profit < -0.01:
            return "exit_4h_negative"

        # Après 8h toujours en négatif : sortie urgente
        if trade_duration_hours >= 8 and current_profit < 0:
            return "exit_8h_negative"

        return None
