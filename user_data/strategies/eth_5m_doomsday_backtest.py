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


class Eth5mDoomsdayBacktest(IStrategy):
    """
    ETH 5分钟末日战车策略回测版
    现货模式回测，用于评估策略逻辑和信号质量
    无法做空，但记录做空信号占比
    """
    
    INTERFACE_VERSION = 3
    timeframe = '5m'
    
    # 激进止盈止损（目标月利润50%）
    stoploss = -0.25  # 25% 止损
    minimal_roi = {
        "0": 0.30,     # 30% 止盈
        "10": 0.15,    # 10分钟后如果盈利15%则退出
        "20": 0.08,    # 20分钟后如果盈利8%则退出
        "40": 0.04,    # 40分钟后如果盈利4%则退出
        "60": 0        # 60分钟后保本退出
    }
    
    process_only_new_candles = True
    use_custom_stoploss = False
    startup_candle_count: int = 100
    can_short = False  # 现货模式
    
    # === 仓位管理 ===
    position_size_pct = DecimalParameter(0.15, 0.35, default=0.25, decimals=2, space="buy")  # 25%仓位
    
    # === 动量信号参数 ===
    momentum_period = IntParameter(3, 8, default=5, space="buy")
    momentum_threshold_long = DecimalParameter(0.005, 0.015, default=0.008, decimals=3, space="buy")
    momentum_threshold_short = DecimalParameter(-0.015, -0.005, default=-0.008, decimals=3, space="buy")
    
    # === RSI参数 ===
    rsi_period = IntParameter(5, 10, default=7, space="buy")
    rsi_overbought = IntParameter(65, 75, default=70, space="sell")
    rsi_oversold = IntParameter(25, 35, default=30, space="buy")
    
    # === 成交量确认 ===
    volume_spike_threshold = DecimalParameter(2.5, 4.5, default=3.0, decimals=1, space="buy")
    
    # === 做空侧重（仅影响信号过滤） ===
    short_bias = DecimalParameter(0.6, 0.9, default=0.75, decimals=2, space="buy")  # 75%做空侧重
    
    # === 突破信号 ===
    breakout_period = IntParameter(10, 20, default=15, space="buy")
    breakout_volume_ratio = DecimalParameter(2.0, 4.0, default=2.5, decimals=1, space="buy")
    
    # === 高频交易优化 ===
    max_daily_trades = IntParameter(10, 25, default=15, space="buy")
    
    # 统计变量
    trade_count = 0
    long_signals = 0
    short_signals = 0
    filtered_long_signals = 0
    
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
        
        # ATR波动率
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
            (dataframe['momentum_5m'] > self.momentum_threshold_long.value) &
            (dataframe['rsi'] > 40) &
            (dataframe['rsi'] < 70)
        )
        
        # 超跌反弹做多
        dataframe['long_reversal'] = (
            (dataframe['rsi'] < self.rsi_oversold.value) &
            (dataframe['rsi'] > dataframe['rsi'].shift(1)) &
            (dataframe['momentum_5m'] > 0.002) &
            (dataframe['bb_position'] < 0.2) &
            dataframe['volume_spike']
        )
        
        # 趋势跟随做多
        dataframe['long_trend'] = (
            (dataframe['ma_fast'] > dataframe['ma_slow']) &
            (dataframe['ma_slow'] > dataframe['ma_trend']) &
            (dataframe['momentum_5m'] > 0.005) &
            (dataframe['close'] > dataframe['ma_fast'])
        )
        
        # 综合做多信号
        dataframe['long_signal_raw'] = (
            dataframe['long_breakout'] |
            dataframe['long_reversal'] |
            dataframe['long_trend']
        )
        
        # ========== 做空信号（仅记录） ==========
        # 弱势突破做空
        dataframe['short_breakout'] = (
            (dataframe['close'] < dataframe['low_15'].shift(1)) &
            (dataframe['volume_ratio'] > self.breakout_volume_ratio.value) &
            (dataframe['momentum_5m'] < self.momentum_threshold_short.value) &
            (dataframe['rsi'] > 30) &
            (dataframe['rsi'] < 80)
        )
        
        # 超买回调做空
        dataframe['short_reversal'] = (
            (dataframe['rsi'] > self.rsi_overbought.value) &
            (dataframe['rsi'] < dataframe['rsi'].shift(1)) &
            (dataframe['momentum_5m'] < -0.002) &
            (dataframe['bb_position'] > 0.8) &
            dataframe['volume_spike']
        )
        
        # 趋势跟随做空
        dataframe['short_trend'] = (
            (dataframe['ma_fast'] < dataframe['ma_slow']) &
            (dataframe['ma_slow'] < dataframe['ma_trend']) &
            (dataframe['momentum_5m'] < -0.005) &
            (dataframe['close'] < dataframe['ma_fast'])
        )
        
        # 综合做空信号
        dataframe['short_signal_raw'] = (
            dataframe['short_breakout'] |
            dataframe['short_reversal'] |
            dataframe['short_trend']
        )
        
        # 统计信号数量
        self.long_signals += dataframe['long_signal_raw'].sum()
        self.short_signals += dataframe['short_signal_raw'].sum()
        
        # ========== 信号过滤 ==========
        # 避免高波动时交易
        dataframe['volatility_high'] = dataframe['atr_pct'] > dataframe['atr_pct'].rolling(window=20).mean() * 1.5
        dataframe['large_move'] = abs(dataframe['momentum_5m']) > 0.03
        
        # 有效条件
        valid_condition = (~dataframe['volatility_high']) & (~dataframe['large_move']) & (dataframe['volume'] > 0)
        
        # 应用做空侧重：随机过滤部分做多信号
        np.random.seed(42)  # 固定随机种子以便回测
        random_filter = np.random.random(len(dataframe)) < self.short_bias.value
        
        # 最终做多信号（现货可执行）
        dataframe['long_signal'] = (
            dataframe['long_signal_raw'] &
            valid_condition &
            (~random_filter)  # 根据做空侧重过滤
        )
        
        # 记录过滤掉的做多信号数量
        self.filtered_long_signals += (dataframe['long_signal_raw'] & valid_condition & random_filter).sum()
        
        # 做空信号（仅记录，不执行）
        dataframe['short_signal'] = (
            dataframe['short_signal_raw'] &
            valid_condition
        )
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 现货只能做多
        dataframe.loc[dataframe['long_signal'], 'enter_long'] = 1
        dataframe.loc[dataframe['long_signal'], 'enter_tag'] = 'long'
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 出场条件
        long_exit = (
            (dataframe['rsi'] > self.rsi_overbought.value) |
            (dataframe['momentum_5m'] < 0) |
            (dataframe['close'] < dataframe['ma_fast'] * 0.985)
        )
        
        stop_loss = dataframe['close'] < dataframe['bb_lower'] * 0.97
        
        dataframe.loc[long_exit | stop_loss, 'exit_long'] = 1
        
        return dataframe
    
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
        self.trade_count += 1
        return True
    
    def bot_start(self, **kwargs):
        """回测开始时调用"""
        print("=" * 60)
        print("末日战车策略回测开始")
        print("=" * 60)
        
    def bot_loop_end(self, **kwargs):
        """回测结束时调用"""
        print("\n" + "=" * 60)
        print("末日战车策略回测统计")
        print("=" * 60)
        print(f"总做多信号数量: {self.long_signals}")
        print(f"总做空信号数量: {self.short_signals}")
        print(f"做空信号占比: {self.short_signals/(self.long_signals+self.short_signals)*100:.1f}%")
        print(f"过滤掉的做多信号（根据做空侧重）: {self.filtered_long_signals}")
        print(f"实际执行的交易数量: {self.trade_count}")
        print("=" * 60)