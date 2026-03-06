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


class Eth5mDoomsday(IStrategy):
    """
    ETH 5分钟末日战车策略
    极端激进，目标：月利润50%+（可能爆仓）
    
    核心特点：
    1. 5分钟超高频交易
    2. 双向交易（多空都做，侧重做空）
    3. 超大仓位（20-30%）
    4. 极高杠杆（10-20倍，需合约配置）
    5. 激进止盈止损（20%-30%）
    
    ⚠️ 风险警告：
    - 可能几天内亏损50-100%本金
    - 仅适用于愿意承担极高风险的小资金
    - 需要合约交易配置
    - 需要低手续费和快速执行
    """
    
    INTERFACE_VERSION = 3
    timeframe = '5m'  # 5分钟超高频
    
    # 极端激进止盈止损（合约交易，名义值）
    stoploss = -0.25  # 25% 止损（高容忍度）
    minimal_roi = {
        "0": 0.30,     # 30% 止盈（高回报）
        "10": 0.15,    # 10分钟后如果盈利15%则退出
        "20": 0.08,    # 20分钟后如果盈利8%则退出
        "40": 0.04,    # 40分钟后如果盈利4%则退出
        "60": 0        # 60分钟后保本退出
    }
    
    process_only_new_candles = True
    use_custom_stoploss = True
    startup_candle_count: int = 100  # 5分钟需要较少初始数据
    
    # 合约交易配置（需在config.json中设置）
    can_short = True  # 允许做空
    leverage_num = 10  # 10倍杠杆（理论值，实际在交易所设置）
    
    # === 仓位管理（极端激进） ===
    position_size_pct = DecimalParameter(0.15, 0.35, default=0.25, decimals=2, space="buy")  # 25%仓位
    
    # === 动量信号参数 ===
    momentum_period = IntParameter(3, 8, default=5, space="buy")  # 5周期动量
    momentum_threshold_long = DecimalParameter(0.005, 0.015, default=0.008, decimals=3, space="buy")
    momentum_threshold_short = DecimalParameter(-0.015, -0.005, default=-0.008, decimals=3, space="buy")
    
    # === 突破信号参数 ===
    breakout_period = IntParameter(10, 20, default=15, space="buy")
    breakout_volume_ratio = DecimalParameter(2.0, 4.0, default=2.5, decimals=1, space="buy")
    
    # === RSI多时间框架 ===
    rsi_period = IntParameter(5, 10, default=7, space="buy")
    rsi_overbought = IntParameter(65, 75, default=70, space="sell")
    rsi_oversold = IntParameter(25, 35, default=30, space="buy")
    
    # === 成交量确认 ===
    volume_spike_threshold = DecimalParameter(2.5, 4.5, default=3.0, decimals=1, space="buy")
    
    # === 做空侧重（熊市优化） ===
    short_bias = DecimalParameter(0.6, 0.9, default=0.75, decimals=2, space="buy")  # 75%概率侧重做空
    enable_short = BooleanParameter(default=True, space="buy")
    enable_long = BooleanParameter(default=True, space="buy")
    
    # === 高频交易优化 ===
    max_daily_trades = IntParameter(15, 30, default=20, space="buy")  # 每日最大20次交易
    min_profit_target = DecimalParameter(0.02, 0.05, default=0.03, decimals=2, space="buy")  # 最小盈利目标3%
    
    # 状态变量
    trade_count_today = 0
    last_trade_date = None
    short_signal_count = 0
    long_signal_count = 0
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ========== 超短线指标 ==========
        # 5分钟动量（极短期）
        dataframe['momentum_5m'] = dataframe['close'].pct_change(periods=self.momentum_period.value)
        dataframe['momentum_3m'] = dataframe['close'].pct_change(periods=3)
        
        # 动量加速
        dataframe['momentum_acc'] = dataframe['momentum_5m'].diff()
        
        # 成交量暴增
        dataframe['volume_ma'] = dataframe['volume'].rolling(window=10).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']
        dataframe['volume_spike'] = dataframe['volume_ratio'] > self.volume_spike_threshold.value
        
        # RSI（快速）
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        
        # 布林带（快速）
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
        
        # 均线（快速）
        dataframe['ma_fast'] = dataframe['close'].rolling(window=7).mean()
        dataframe['ma_slow'] = dataframe['close'].rolling(window=21).mean()
        dataframe['ma_trend'] = dataframe['close'].rolling(window=50).mean()
        
        # ========== 做多信号 ==========
        # 强势突破做多
        dataframe['long_breakout'] = (
            (dataframe['close'] > dataframe['high_15'].shift(1)) &
            (dataframe['volume_ratio'] > self.breakout_volume_ratio.value) &
            (dataframe['momentum_5m'] > self.momentum_threshold_long.value) &
            (dataframe['rsi'] > 40) &  # 不在超卖区
            (dataframe['rsi'] < 70)   # 不在超买区
        )
        
        # 超跌反弹做多
        dataframe['long_reversal'] = (
            (dataframe['rsi'] < self.rsi_oversold.value) &
            (dataframe['rsi'] > dataframe['rsi'].shift(1)) &  # RSI开始上升
            (dataframe['momentum_5m'] > 0.002) &  # 开始有正动量
            (dataframe['bb_position'] < 0.2) &  # 价格在布林带下部
            (dataframe['volume_spike'])  # 成交量确认
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
            self.enable_long.value &
            (
                dataframe['long_breakout'] |
                dataframe['long_reversal'] |
                dataframe['long_trend']
            )
        )
        
        # ========== 做空信号（侧重） ==========
        # 弱势突破做空
        dataframe['short_breakout'] = (
            (dataframe['close'] < dataframe['low_15'].shift(1)) &
            (dataframe['volume_ratio'] > self.breakout_volume_ratio.value) &
            (dataframe['momentum_5m'] < self.momentum_threshold_short.value) &
            (dataframe['rsi'] > 30) &  # 不在超卖区
            (dataframe['rsi'] < 80)   # 可能超买
        )
        
        # 超买回调做空
        dataframe['short_reversal'] = (
            (dataframe['rsi'] > self.rsi_overbought.value) &
            (dataframe['rsi'] < dataframe['rsi'].shift(1)) &  # RSI开始下降
            (dataframe['momentum_5m'] < -0.002) &  # 开始有负动量
            (dataframe['bb_position'] > 0.8) &  # 价格在布林带上部
            (dataframe['volume_spike'])  # 成交量确认
        )
        
        # 趋势跟随做空
        dataframe['short_trend'] = (
            (dataframe['ma_fast'] < dataframe['ma_slow']) &
            (dataframe['ma_slow'] < dataframe['ma_trend']) &
            (dataframe['momentum_5m'] < -0.005) &
            (dataframe['close'] < dataframe['ma_fast'])
        )
        
        # 综合做空信号（侧重）
        dataframe['short_signal'] = (
            self.enable_short.value &
            (
                dataframe['short_breakout'] |
                dataframe['short_reversal'] |
                dataframe['short_trend']
            )
        )
        
        # ========== 信号过滤 ==========
        # 避免高波动时交易
        dataframe['volatility_high'] = dataframe['atr_pct'] > dataframe['atr_pct'].rolling(window=20).mean() * 1.5
        
        # 价格变化过大时暂停交易
        dataframe['large_move'] = abs(dataframe['momentum_5m']) > 0.03  # 5分钟波动超过3%
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 检查今日交易次数限制
        current_date = pd.Timestamp.now().normalize()
        if current_date != self.last_trade_date:
            self.trade_count_today = 0
            self.last_trade_date = current_date
            self.short_signal_count = 0
            self.long_signal_count = 0
        
        # 交易次数限制
        trade_limit_ok = self.trade_count_today < self.max_daily_trades.value
        
        # 做多条件
        long_condition = (
            trade_limit_ok &
            dataframe['long_signal'] &
            (~dataframe['volatility_high']) &
            (~dataframe['large_move']) &
            (dataframe['volume'] > 0)
        )
        
        # 做空条件（侧重）
        short_condition = (
            trade_limit_ok &
            dataframe['short_signal'] &
            (~dataframe['volatility_high']) &
            (~dataframe['large_move']) &
            (dataframe['volume'] > 0)
        )
        
        # 应用做空侧重：随机过滤部分做多信号
        if self.short_bias.value > 0.5:
            # 75%概率侧重做空：随机丢弃部分做多信号
            np.random.seed(42)  # 固定随机种子以便回测
            random_filter = np.random.random(len(dataframe)) < self.short_bias.value
            long_condition = long_condition & (~random_filter)
        
        # 设置进场信号
        dataframe.loc[long_condition, 'enter_long'] = 1
        dataframe.loc[long_condition, 'enter_tag'] = 'long'
        
        dataframe.loc[short_condition, 'enter_short'] = 1
        dataframe.loc[short_condition, 'enter_tag'] = 'short'
        
        # 统计信号数量
        self.long_signal_count += long_condition.sum()
        self.short_signal_count += short_condition.sum()
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 做多出场条件
        long_exit = (
            (dataframe['rsi'] > self.rsi_overbought.value) |  # RSI超买
            (dataframe['momentum_5m'] < 0) |  # 动量转负
            (dataframe['close'] < dataframe['ma_fast'] * 0.985)  # 跌破快速均线1.5%
        )
        
        # 做空出场条件
        short_exit = (
            (dataframe['rsi'] < self.rsi_oversold.value) |  # RSI超卖
            (dataframe['momentum_5m'] > 0) |  # 动量转正
            (dataframe['close'] > dataframe['ma_fast'] * 1.015)  # 突破快速均线1.5%
        )
        
        # 止损出场（宽松）
        stop_loss_long = dataframe['close'] < dataframe['bb_lower'] * 0.97
        stop_loss_short = dataframe['close'] > dataframe['bb_upper'] * 1.03
        
        dataframe.loc[long_exit | stop_loss_long, 'exit_long'] = 1
        dataframe.loc[short_exit | stop_loss_short, 'exit_short'] = 1
        
        return dataframe
    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> Optional[float]:
        # 极端激进的止损策略
        # 深度亏损才止损，让高止盈有机会触发
        
        # 做空交易
        if trade.is_short:
            # 做空时价格上涨为亏损
            if current_profit < -0.20:  # 亏损超过20%
                return -0.20
            elif current_profit > 0.15:  # 盈利15%后
                return current_profit - 0.08  # 移动止损保留8%利润
            elif current_profit > 0.08:  # 盈利8%后
                return current_profit - 0.04  # 移动止损保留4%利润
        # 做多交易
        else:
            if current_profit < -0.20:  # 亏损超过20%
                return -0.20
            elif current_profit > 0.15:  # 盈利15%后
                return current_profit - 0.08  # 移动止损保留8%利润
            elif current_profit > 0.08:  # 盈利8%后
                return current_profit - 0.04  # 移动止损保留4%利润
        
        return None  # 使用固定止损
    
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                           proposed_stake: float, min_stake: Optional[float], max_stake: float,
                           leverage: float, entry_tag: Optional[str], side: str,
                           **kwargs) -> float:
        # 极端激进仓位：25%本金
        wallet = self.wallets.get_total_stake_amount()
        max_stake_amount = wallet * self.position_size_pct.value
        
        # 根据信号类型微调
        if entry_tag == 'short' and self.short_bias.value > 0.7:
            # 做空侧重时，做空仓位可以更大
            max_stake_amount = wallet * (self.position_size_pct.value * 1.2)
        elif entry_tag == 'long' and self.short_bias.value > 0.7:
            # 做空侧重时，做多仓位减小
            max_stake_amount = wallet * (self.position_size_pct.value * 0.8)
        
        return min(proposed_stake, max_stake_amount)
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        # 理论杠杆设置，实际在交易所配置
        return 10.0  # 10倍杠杆
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                           time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                           side: str, **kwargs) -> bool:
        # 确认交易前检查
        self.trade_count_today += 1
        return True