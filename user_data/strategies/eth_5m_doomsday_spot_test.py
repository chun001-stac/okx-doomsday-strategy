# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these imports ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Union

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, BooleanParameter, CategoricalParameter
import talib.abstract as ta


class Eth5mDoomsdaySpotTest(IStrategy):
    """
    ETH 5分钟末日战车策略（现货测试版）
    现货模式下只能做多，用于测试信号逻辑
    实盘需要合约交易配置
    """
    
    INTERFACE_VERSION = 3
    timeframe = '5m'
    
    # 激进止盈止损（现货测试用较小值）
    stoploss = -0.15  # 15% 止损
    minimal_roi = {
        "0": 0.20,     # 20% 止盈
        "10": 0.10,    # 10分钟后如果盈利10%则退出
        "20": 0.05,    # 20分钟后如果盈利5%则退出
        "40": 0.02,    # 40分钟后如果盈利2%则退出
        "60": 0        # 60分钟后保本退出
    }
    
    process_only_new_candles = True
    use_custom_stoploss = True
    startup_candle_count: int = 100
    can_short = False  # 现货模式不支持做空
    
    # === 仓位管理 ===
    position_size_pct = DecimalParameter(0.10, 0.25, default=0.15, decimals=2, space="buy")  # 15%仓位
    
    # === 动量信号参数 ===
    momentum_period = IntParameter(3, 8, default=5, space="buy")
    momentum_threshold = DecimalParameter(0.005, 0.015, default=0.008, decimals=3, space="buy")
    
    # === 突破信号参数 ===
    breakout_period = IntParameter(10, 20, default=15, space="buy")
    breakout_volume_ratio = DecimalParameter(2.0, 4.0, default=2.5, decimals=1, space="buy")
    
    # === RSI参数 ===
    rsi_period = IntParameter(5, 10, default=7, space="buy")
    rsi_overbought = IntParameter(65, 75, default=70, space="sell")
    rsi_oversold = IntParameter(25, 35, default=30, space="buy")
    
    # === 成交量确认 ===
    volume_spike_threshold = DecimalParameter(2.5, 4.5, default=3.0, decimals=1, space="buy")
    
    # === 做空侧重（仅记录，现货不执行） ===
    short_bias = DecimalParameter(0.6, 0.9, default=0.75, decimals=2, space="buy")  # 记录做空倾向
    
    # === 高频交易优化 ===
    max_daily_trades = IntParameter(10, 25, default=15, space="buy")
    
    # 状态变量
    trade_count_today = 0
    last_trade_date = None
    short_signal_count = 0
    long_signal_count = 0
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ========== 超短线指标 ==========
        dataframe['momentum_5m'] = dataframe['close'].pct_change(periods=self.momentum_period.value)
        dataframe['momentum_3m'] = dataframe['close'].pct_change(periods=3)
        dataframe['momentum_acc'] = dataframe['momentum_5m'].diff()
        
        # 成交量
        dataframe['volume_ma'] = dataframe['volume'].rolling(window=10).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']
        dataframe['volume_spike'] = dataframe['volume_ratio'] > self.volume_spike_threshold.value
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        
        # 布林带
        bb = ta.BBANDS(dataframe, timeperiod=15, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_upper'] = bb['upperband']
        dataframe['bb_middle'] = bb['middleband']
        dataframe['bb_lower'] = bb['lowerband']
        dataframe['bb_position'] = (dataframe['close'] - dataframe['bb_lower']) / (dataframe['bb_upper'] - dataframe['bb_lower'])
        dataframe['bb_position'] = dataframe['bb_position'].clip(0, 1)
        
        # 突破信号
        dataframe['high_15'] = dataframe['high'].rolling(window=self.breakout_period.value).max()
        dataframe['low_15'] = dataframe['low'].rolling(window=self.breakout_period.value).min()
        
        # ATR
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=10)
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close']
        
        # 均线
        dataframe['ma_fast'] = dataframe['close'].rolling(window=7).mean()
        dataframe['ma_slow'] = dataframe['close'].rolling(window=21).mean()
        dataframe['ma_trend'] = dataframe['close'].rolling(window=50).mean()
        
        # ========== 做多信号 ==========
        # 强势突破做多
        dataframe['long_breakout'] = (
            (dataframe['close'] > dataframe['high_15'].shift(1)) &
            (dataframe['volume_ratio'] > self.breakout_volume_ratio.value) &
            (dataframe['momentum_5m'] > self.momentum_threshold.value) &
            (dataframe['rsi'] > 40) &
            (dataframe['rsi'] < 70)
        )
        
        # 超跌反弹做多
        dataframe['long_reversal'] = (
            (dataframe['rsi'] < self.rsi_oversold.value) &
            (dataframe['rsi'] > dataframe['rsi'].shift(1)) &
            (dataframe['momentum_5m'] > 0.002) &
            (dataframe['bb_position'] < 0.2) &
            (dataframe['volume_spike'])
        )
        
        # 趋势跟随做多
        dataframe['long_trend'] = (
            (dataframe['ma_fast'] > dataframe['ma_slow']) &
            (dataframe['ma_slow'] > dataframe['ma_trend']) &
            (dataframe['momentum_5m'] > 0.005) &
            (dataframe['close'] > dataframe['ma_fast'])
        )
        
        # 综合做多信号
        dataframe['long_signal'] = (
            dataframe['long_breakout'] |
            dataframe['long_reversal'] |
            dataframe['long_trend']
        )
        
        # ========== 做空信号（仅记录，不执行） ==========
        # 弱势突破做空（记录用）
        dataframe['short_breakout_signal'] = (
            (dataframe['close'] < dataframe['low_15'].shift(1)) &
            (dataframe['volume_ratio'] > self.breakout_volume_ratio.value) &
            (dataframe['momentum_5m'] < -0.005) &
            (dataframe['rsi'] > 30) &
            (dataframe['rsi'] < 80)
        )
        
        # 超买回调做空（记录用）
        dataframe['short_reversal_signal'] = (
            (dataframe['rsi'] > self.rsi_overbought.value) &
            (dataframe['rsi'] < dataframe['rsi'].shift(1)) &
            (dataframe['momentum_5m'] < -0.002) &
            (dataframe['bb_position'] > 0.8) &
            (dataframe['volume_spike'])
        )
        
        # 记录做空信号数量
        dataframe['short_signal'] = dataframe['short_breakout_signal'] | dataframe['short_reversal_signal']
        
        # ========== 信号过滤 ==========
        dataframe['volatility_high'] = dataframe['atr_pct'] > dataframe['atr_pct'].rolling(window=20).mean() * 1.5
        dataframe['large_move'] = abs(dataframe['momentum_5m']) > 0.03
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 检查今日交易次数
        current_date = pd.Timestamp.now().normalize()
        if current_date != self.last_trade_date:
            self.trade_count_today = 0
            self.last_trade_date = current_date
            self.short_signal_count = 0
            self.long_signal_count = 0
        
        trade_limit_ok = self.trade_count_today < self.max_daily_trades.value
        
        # 做多条件（现货仅做多）
        long_condition = (
            trade_limit_ok &
            dataframe['long_signal'] &
            (~dataframe['volatility_high']) &
            (~dataframe['large_move']) &
            (dataframe['volume'] > 0)
        )
        
        # 应用做空侧重：随机过滤部分做多信号
        if self.short_bias.value > 0.5:
            np.random.seed(42)
            random_filter = np.random.random(len(dataframe)) < self.short_bias.value
            long_condition = long_condition & (~random_filter)
        
        dataframe.loc[long_condition, 'enter_long'] = 1
        dataframe.loc[long_condition, 'enter_tag'] = 'long'
        
        # 统计信号
        self.long_signal_count += long_condition.sum()
        self.short_signal_count += dataframe['short_signal'].sum()
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 做多出场条件
        long_exit = (
            (dataframe['rsi'] > self.rsi_overbought.value) |
            (dataframe['momentum_5m'] < 0) |
            (dataframe['close'] < dataframe['ma_fast'] * 0.985)
        )
        
        stop_loss = dataframe['close'] < dataframe['bb_lower'] * 0.97
        
        dataframe.loc[long_exit | stop_loss, 'exit_long'] = 1
        
        return dataframe
    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> Optional[float]:
        if current_profit < -0.15:
            return -0.15
        elif current_profit > 0.10:
            return current_profit - 0.06
        elif current_profit > 0.05:
            return current_profit - 0.03
        
        return None
    
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                           proposed_stake: float, min_stake: Optional[float], max_stake: float,
                           leverage: float, entry_tag: Optional[str], side: str,
                           **kwargs) -> float:
        wallet = self.wallets.get_total_stake_amount()
        max_stake_amount = wallet * self.position_size_pct.value
        return min(proposed_stake, max_stake_amount)
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        return 1.0
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                           time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                           side: str, **kwargs) -> bool:
        self.trade_count_today += 1
        return True