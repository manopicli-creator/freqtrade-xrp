from freqtrade.strategy import IStrategy, IntParameter
from pandas import DataFrame
from datetime import datetime, timedelta
from typing import Optional
import talib.abstract as ta
import pandas as pd

class XRPStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '15m'
    startup_candle_count = 200

    stoploss = -0.03

    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    use_custom_stoploss = False

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

    # Slider 1–33  → score >= 3  (sélectif)
    # Slider 34–66 → score >= 2  (modéré)
    # Slider 67–100 → score >= 1 (agressif)
    buy_score_threshold = IntParameter(1, 100, default=20, space='buy', load=True)

    daily_drawdown_limit = -0.03
    pair_cooldown_hours = 4

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        informative = [(pair, '5m') for pair in pairs]
        informative += [(pair, '1h') for pair in pairs]
        return informative

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

        dataframe['signal_score'] = 0
        dataframe.loc[dataframe['adx'] > 20, 'signal_score'] += 1
        dataframe.loc[dataframe['adx'] > 30, 'signal_score'] += 1

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

        dataframe.loc[
            (dataframe['5m_rsi'] > 45) & (dataframe['5m_rsi'] < 60),
            'signal_score'
        ] += 1
        dataframe.loc[
            dataframe['5m_ema20'] > dataframe['5m_ema50'],
            'signal_score'
        ] += 1

        inf1h = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1h')
        if len(inf1h) > 0:
            inf1h['ema20_1h'] = ta.EMA(inf1h, timeperiod=20)
            inf1h['ema50_1h'] = ta.EMA(inf1h, timeperiod=50)
            inf1h['ema200_1h'] = ta.EMA(inf1h, timeperiod=200)
            inf1h['rsi_1h'] = ta.RSI(inf1h, timeperiod=14)
            inf1h['date'] = pd.to_datetime(inf1h['date'])
            inf1h_15 = inf1h[['date', 'ema20_1h', 'ema50_1h', 'ema200_1h', 'rsi_1h']].copy()
            inf1h_15['date'] = inf1h_15['date'].dt.floor('15min')
            dataframe = dataframe.merge(inf1h_15, on='date', how='left')
        else:
            dataframe['ema20_1h'] = float('nan')
            dataframe['ema50_1h'] = float('nan')
            dataframe['ema200_1h'] = float('nan')
            dataframe['rsi_1h'] = float('nan')

        dataframe.ffill(inplace=True)
        return dataframe

    def _score_threshold_from_slider(self) -> int:
        v = self.buy_score_threshold.value
        if v <= 33:
            return 3
        elif v <= 66:
            return 2
        else:
            return 1

    def _is_circuit_breaker_active(self, current_time: datetime) -> bool:
        if self.daily_drawdown_limit >= 0:
            return False
        try:
            from freqtrade.persistence import Trade
            start_of_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            closed_today = Trade.get_trades_proxy(is_open=False, open_date=start_of_day)
            daily_pnl = sum(t.close_profit_abs for t in closed_today if t.close_profit_abs)
            current_balance = self.wallets.get_free('USDT') + self.wallets.get_used('USDT')
            if current_balance <= 0:
                return False
            drawdown = daily_pnl / current_balance
            return drawdown < self.daily_drawdown_limit
        except Exception:
            return False

    def _is_pair_in_cooldown(self, pair: str, current_time: datetime) -> bool:
        if self.pair_cooldown_hours <= 0:
            return False
        try:
            from freqtrade.persistence import Trade
            cutoff = current_time - timedelta(hours=self.pair_cooldown_hours)
            recent_trades = Trade.get_trades_proxy(is_open=False, pair=pair)
            for t in recent_trades:
                if t.close_date_utc and t.close_date_utc >= cutoff:
                    if t.exit_reason and 'stop_loss' in t.exit_reason.lower():
                        return True
        except Exception:
            pass
        return False

    def _had_recent_trailing_stop(self, pair: str, current_time: datetime) -> bool:
        try:
            from freqtrade.persistence import Trade
            cutoff = current_time - timedelta(hours=2)
            recent_trades = Trade.get_trades_proxy(is_open=False, pair=pair)
            for t in recent_trades:
                if t.close_date_utc and t.close_date_utc >= cutoff:
                    if t.exit_reason == 'trailing_stop_loss' and t.close_profit > 0:
                        return True
        except Exception:
            pass
        return False

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        min_score = self._score_threshold_from_slider()

        dataframe.loc[
            (
                # 1. Filtre tendance 1h
                (dataframe['close'] > dataframe['ema200_1h']) &

                # 2. Bougie verte obligatoire
                (dataframe['close'] > dataframe['open']) &

                # 3. Score signal selon slider
                (dataframe['signal_score'] >= min_score) &

                # 4. Conditions techniques de base
                (dataframe['adx'] > self.buy_adx_min.value) &
                (dataframe['5m_ema20'] > dataframe['5m_ema50']) &
                (dataframe['5m_rsi'] > self.buy_rsi_min.value) &
                (dataframe['5m_rsi'] < self.buy_rsi_max.value) &
                (dataframe['5m_volume_ok']) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: Optional[str], side: str, **kwargs) -> bool:
        if self._is_circuit_breaker_active(current_time):
            return False
        if self._is_pair_in_cooldown(pair, current_time):
            return False
        return True

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['rsi_1h'] < 40) &
                (dataframe['ema20_1h'] < dataframe['ema50_1h'])
            ),
            'exit_long'] = 1
        return dataframe

    def custom_stake_amount(self, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float],
                            max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, pair: str, **kwargs) -> float:
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if len(dataframe) == 0:
                return proposed_stake
            score = int(dataframe.iloc[-1]['signal_score'])
        except Exception:
            return proposed_stake

        if score >= 4:
            pct = 1.20
        elif score >= 2:
            pct = 1.00
        else:
            pct = 0.80

        if self._had_recent_trailing_stop(pair, current_time):
            pct = min(pct * 1.25, 1.50)

        stake = proposed_stake * pct

        if min_stake and stake < min_stake:
            stake = min_stake
        if stake > max_stake:
            stake = max_stake

        return stake

    def custom_exit(self, pair: str, trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        hours = (current_time - trade.open_date_utc).total_seconds() / 3600

        if hours >= 1 and current_profit < -0.01:
            return "exit_1h_neg1pct"

        if hours >= 2 and current_profit < -0.005:
            return "exit_2h_neg05pct"

        if hours >= 3 and current_profit < 0:
            return "exit_3h_negative"

        return None
