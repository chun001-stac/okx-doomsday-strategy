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


class Eth15mHighFreqGrid(IStrategy):
    """
    ETH 15分钟高频混合网格策略
    方案D：密集网格 + 高频量化因子 + 动态仓位
    
    核心特点：
    1. 15分钟时间框架 - 高频交易机会
    2. 密集网格（15层，0.3%间距）
    3. 多种量化因子：动量、突破、成交量、ATR、RSI等
    4. 动态仓位管理（根据波动率调整）
    5. 多市场状态适应（趋势/震荡/突破）
    
    目标：月利润50%（激进设置）
    """
    
    INTERFACE_VERSION = 3
    timeframe = '15m'  # 高频交易
    
    # 激进止损止盈设置（目标月利润50%）
    stoploss = -0.08  # 8% 止损（容忍更大回撤）
    minimal_roi = {
        "0": 0.15,     # 15% 止盈（高回报目标）
        "30": 0.08,    # 30分钟后如果盈利8%则退出
        "60": 0.04,    # 60分钟后如果盈利4%则退出
        "180": 0       # 180分钟后保本退出
    }
    
    # 高频交易需要快速响应
    process_only_new_candles = True
    use_custom_stoploss = True
    startup_candle_count: int = 150  # 15分钟需要更多初始数据
    
    # === 密集网格参数 ===
    grid_levels = IntParameter(15, 25, default=20, space="buy")  # 20层超密集网格
    grid_spacing_pct = DecimalParameter(0.0015, 0.003, default=0.002, decimals=3, space="buy")  # 0.2%间距
    
    # 网格仓位管理（激进）
    base_grid_position_pct = DecimalParameter(0.05, 0.12, default=0.08, decimals=3, space="buy")
    grid_progressive_position = BooleanParameter(default=True, space="buy")  # 是否渐进加仓
    
    # === 量化因子1：动量指标 ===
    momentum_period = IntParameter(5, 15, default=8, space="buy")  # 动量周期
    momentum_threshold = DecimalParameter(0.003, 0.008, default=0.005, decimals=4, space="buy")  # 动量阈值提高至0.5%
    
    # === 量化因子2：突破信号 ===
    breakout_period = IntParameter(10, 25, default=15, space="buy")  # 突破观察周期
    breakout_volume_ratio = DecimalParameter(2.0, 4.0, default=2.8, decimals=1, space="buy")  # 突破成交量要求提高
    
    # === 量化因子3：成交量分析 ===
    volume_ma_period = IntParameter(10, 20, default=15, space="buy")
    volume_spike_threshold = DecimalParameter(2.5, 4.5, default=3.0, decimals=1, space="buy")  # 成交量暴增要求提高
    
    # === 量化因子4：波动率分析 ===
    atr_period = IntParameter(10, 20, default=14, space="buy")
    atr_multiplier = DecimalParameter(1.0, 2.0, default=1.5, decimals=1, space="buy")
    
    # === 量化因子5：RSI多时间框架 ===
    rsi_fast_period = IntParameter(5, 10, default=7, space="buy")
    rsi_slow_period = IntParameter(12, 20, default=14, space="buy")
    rsi_oversold = IntParameter(28, 38, default=32, space="buy")
    rsi_overbought = IntParameter(62, 72, default=68, space="sell")
    
    # === 量化因子6：价格位置 ===
    bb_period = IntParameter(18, 22, default=20, space="buy")
    bb_std = DecimalParameter(1.8, 2.2, default=2.0, decimals=1, space="buy")
    
    # === 市场状态判断 ===
    market_state_method = CategoricalParameter(['auto', 'trending', 'ranging'], default='auto', space="buy")
    
    # === 动态仓位管理 ===
    dynamic_position_enabled = BooleanParameter(default=True, space="buy")
    volatility_scaling = BooleanParameter(default=True, space="buy")
    
    # === 高频交易优化 ===
    max_daily_trades = IntParameter(10, 30, default=20, space="buy")  # 每日最大交易次数提高至20
    min_profit_per_trade = DecimalParameter(0.003, 0.015, default=0.008, decimals=3, space="buy")  # 最小盈利目标提高
    
    # 状态变量
    current_grid_prices = []
    trade_count_today = 0
    last_trade_date = None
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ========== 量化因子1：动量指标 ==========
        # 价格动量（最近N根K线的收益率）
        dataframe['momentum'] = dataframe['close'].pct_change(periods=self.momentum_period.value)
        
        # 动量加速（动量变化率）
        dataframe['momentum_acc'] = dataframe['momentum'].diff()
        
        # 价格变化方向一致性
        dataframe['price_up_count'] = (dataframe['close'] > dataframe['close'].shift(1)).rolling(window=5).sum()
        dataframe['price_down_count'] = (dataframe['close'] < dataframe['close'].shift(1)).rolling(window=5).sum()
        dataframe['price_direction'] = dataframe['price_up_count'] - dataframe['price_down_count']
        
        # ========== 量化因子2：突破信号 ==========
        # 近期高点突破
        dataframe['high_breakout'] = dataframe['high'].rolling(window=self.breakout_period.value).max()
        dataframe['low_breakout'] = dataframe['low'].rolling(window=self.breakout_period.value).min()
        
        # 突破确认
        dataframe['breakout_up'] = (
            (dataframe['close'] > dataframe['high_breakout'].shift(1)) &
            (dataframe['volume'] > dataframe['volume'].rolling(window=20).mean() * self.breakout_volume_ratio.value)
        )
        
        dataframe['breakout_down'] = (
            (dataframe['close'] < dataframe['low_breakout'].shift(1)) &
            (dataframe['volume'] > dataframe['volume'].rolling(window=20).mean() * self.breakout_volume_ratio.value)
        )
        
        # ========== 量化因子3：成交量分析 ==========
        dataframe['volume_ma'] = dataframe['volume'].rolling(window=self.volume_ma_period.value).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']
        dataframe['volume_spike'] = dataframe['volume_ratio'] > self.volume_spike_threshold.value
        
        # 量价关系
        dataframe['volume_price_corr'] = dataframe['volume'].rolling(window=10).corr(dataframe['close'])
        
        # ========== 量化因子4：波动率分析 ==========
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period.value)
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close']
        dataframe['volatility'] = dataframe['atr_pct'].rolling(window=20).mean()
        
        # 波动率状态（高/中/低）
        dataframe['volatility_high'] = dataframe['atr_pct'] > dataframe['volatility'] * 1.5
        dataframe['volatility_low'] = dataframe['atr_pct'] < dataframe['volatility'] * 0.7
        
        # ========== 量化因子5：RSI多时间框架 ==========
        dataframe['rsi_fast'] = ta.RSI(dataframe, timeperiod=self.rsi_fast_period.value)
        dataframe['rsi_slow'] = ta.RSI(dataframe, timeperiod=self.rsi_slow_period.value)
        
        # RSI背离
        dataframe['rsi_divergence'] = (
            (dataframe['close'] < dataframe['close'].shift(5)) &
            (dataframe['rsi_fast'] > dataframe['rsi_fast'].shift(5))
        )
        
        # ========== 量化因子6：价格位置 ==========
        # 布林带
        bb = ta.BBANDS(dataframe, timeperiod=self.bb_period.value, nbdevup=self.bb_std.value, nbdevdn=self.bb_std.value)
        dataframe['bb_upper'] = bb['upperband']
        dataframe['bb_middle'] = bb['middleband']
        dataframe['bb_lower'] = bb['lowerband']
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']
        
        # 价格在布林带中的位置（0-1，0在下轨，1在上轨）
        dataframe['bb_position'] = (dataframe['close'] - dataframe['bb_lower']) / (dataframe['bb_upper'] - dataframe['bb_lower'])
        dataframe['bb_position'] = dataframe['bb_position'].clip(0, 1)
        
        # ========== 市场状态判断 ==========
        # 趋势强度（ADX）
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        
        # 移动平均线趋势
        dataframe['ma_fast'] = dataframe['close'].rolling(window=9).mean()
        dataframe['ma_slow'] = dataframe['close'].rolling(window=21).mean()
        dataframe['ma_trend'] = dataframe['close'].rolling(window=50).mean()
        
        dataframe['ma_fast_up'] = dataframe['ma_fast'] > dataframe['ma_fast'].shift(1)
        dataframe['ma_slow_up'] = dataframe['ma_slow'] > dataframe['ma_slow'].shift(1)
        
        # 市场状态判断
        trending_condition = (
            (dataframe['adx'] > 25) &
            (dataframe['bb_width'] > 0.04) &
            dataframe['ma_fast_up'] &
            (abs(dataframe['momentum']) > 0.002)
        )
        
        ranging_condition = (
            (dataframe['adx'] < 20) &
            (dataframe['bb_width'] < 0.03) &
            (dataframe['bb_position'].between(0.2, 0.8)) &
            (dataframe['volatility'] < 0.008)
        )
        
        breakout_condition = (
            dataframe['breakout_up'] |
            dataframe['breakout_down']
        )
        
        dataframe['market_state'] = 'neutral'
        dataframe.loc[trending_condition, 'market_state'] = 'trending'
        dataframe.loc[ranging_condition, 'market_state'] = 'ranging'
        dataframe.loc[breakout_condition, 'market_state'] = 'breakout'
        
        # ========== 密集网格水平计算 ==========
        # 基于布林带计算网格水平
        grid_range = dataframe['bb_upper'] - dataframe['bb_lower']
        self.current_grid_prices = []
        
        for i in range(self.grid_levels.value):
            level_pct = i / (self.grid_levels.value - 1) if self.grid_levels.value > 1 else 0.5
            grid_price = dataframe['bb_lower'] + grid_range * level_pct
            dataframe[f'grid_level_{i}'] = grid_price
        
        # 当前价格最近的网格水平
        dataframe['nearest_grid_level'] = 0
        dataframe['distance_to_grid'] = 0
        
        for i in range(self.grid_levels.value):
            distance = abs(dataframe['close'] - dataframe[f'grid_level_{i}']) / dataframe['close']
            is_closer = distance < dataframe['distance_to_grid']
            dataframe.loc[is_closer, 'nearest_grid_level'] = i
            dataframe.loc[is_closer, 'distance_to_grid'] = distance
        
        # ========== 综合信号生成 ==========
        # 动量信号
        dataframe['momentum_signal'] = (
            (dataframe['momentum'] > self.momentum_threshold.value) &
            (dataframe['momentum_acc'] > 0) &
            (dataframe['price_direction'] > 2)
        )
        
        # 成交量确认信号
        dataframe['volume_signal'] = (
            dataframe['volume_spike'] &
            (dataframe['volume_price_corr'] > 0.3) &
            (dataframe['close'] > dataframe['close'].shift(1))
        )
        
        # RSI信号
        dataframe['rsi_signal'] = (
            (dataframe['rsi_fast'] < self.rsi_oversold.value) &
            (dataframe['rsi_fast'] > dataframe['rsi_fast'].shift(1)) &
            (dataframe['rsi_slow'] < 45)
        )
        
        # 网格买入信号（价格接近网格支撑位）
        dataframe['grid_buy_signal'] = (
            (dataframe['market_state'] == 'ranging') &
            (dataframe['nearest_grid_level'] <= self.grid_levels.value // 3) &  # 在下1/3网格区域
            (dataframe['distance_to_grid'] < self.grid_spacing_pct.value * 0.5) &  # 接近网格水平
            (dataframe['rsi_fast'] < self.rsi_oversold.value + 5)
        )
        
        # 趋势买入信号
        dataframe['trend_buy_signal'] = (
            (dataframe['market_state'] == 'trending') &
            dataframe['momentum_signal'] &
            dataframe['volume_signal'] &
            (dataframe['close'] > dataframe['ma_fast']) &
            (dataframe['ma_fast'] > dataframe['ma_slow'])
        )
        
        # 突破买入信号
        dataframe['breakout_buy_signal'] = (
            (dataframe['market_state'] == 'breakout') &
            dataframe['breakout_up'] &
            (dataframe['volume_ratio'] > 2.0) &
            (dataframe['momentum'] > 0.005)
        )
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 检查今日交易次数限制
        current_date = pd.Timestamp.now().normalize()
        if current_date != self.last_trade_date:
            self.trade_count_today = 0
            self.last_trade_date = current_date
        
        # 交易次数限制
        trade_limit_ok = self.trade_count_today < self.max_daily_trades.value
        
        # 综合买入条件
        buy_condition = (
            trade_limit_ok &
            (
                dataframe['grid_buy_signal'] |
                dataframe['trend_buy_signal'] |
                dataframe['breakout_buy_signal']
            ) &
            (dataframe['volume'] > 0) &
            (~dataframe['volatility_high'])  # 避免高波动时入场
        )
        
        dataframe.loc[buy_condition, 'enter_long'] = 1
        
        # 设置交易标签（用于仓位管理）
        conditions = [
            (dataframe['grid_buy_signal'], 'grid'),
            (dataframe['trend_buy_signal'], 'trend'),
            (dataframe['breakout_buy_signal'], 'breakout'),
        ]
        
        for condition, tag in conditions:
            dataframe.loc[buy_condition & condition, 'enter_tag'] = tag
        
        # 如果没有标签，使用默认
        dataframe.loc[buy_condition & dataframe['enter_tag'].isna(), 'enter_tag'] = 'default'
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 网格出场：放宽条件，让利润奔跑
        grid_exit = (
            (dataframe['market_state'] == 'ranging') &
            (
                (dataframe['bb_position'] > 0.85) |  # 接近布林带上轨（从0.7提高到0.85）
                (dataframe['rsi_fast'] > self.rsi_overbought.value)  # RSI进入超买区
            )
        )
        
        # 趋势出场：只在明显反转时出场
        trend_exit = (
            (dataframe['market_state'] == 'trending') &
            (
                (dataframe['momentum'] < -0.01) |  # 动量明显转负（从0提高到-0.01）
                (dataframe['close'] < dataframe['ma_fast'] * 0.97)  # 大幅跌破快速均线3%
            )
        )
        
        # 突破出场：放宽回踩条件
        breakout_exit = (
            (dataframe['market_state'] == 'breakout') &
            (
                (dataframe['close'] < dataframe['high_breakout'] * 0.97) |  # 大幅回踩突破位3%（从1%放宽到3%）
                (dataframe['volume_ratio'] < 0.8)  # 成交量显著萎缩
            )
        )
        
        # 止损出场（放宽条件，减少频繁止损）
        stop_loss = (
            (dataframe['close'] < dataframe['bb_lower'] * 0.95) |  # 跌破布林带下轨5%（放宽）
            (dataframe['volatility_high'] & (dataframe['momentum'] < -0.03))  # 高波动且大幅下跌3%
        )
        
        dataframe.loc[grid_exit | trend_exit | breakout_exit | stop_loss, 'exit_long'] = 1
        
        return dataframe
    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> Optional[float]:
        # 激进止损策略：只在深度亏损时止损，让止盈策略发挥作用
        # 月利润50%目标需要容忍更大回撤
        
        # 深度止损：亏损超过15%时强制止损
        if current_profit < -0.15:
            return -0.15
        
        # 盈利后的移动止损（宽松）
        if current_profit > 0.08:  # 盈利8%后
            # 移动止损：保留5%利润
            return current_profit - 0.05
        elif current_profit > 0.04:  # 盈利4%后
            # 移动止损：保留2%利润
            return current_profit - 0.02
        elif current_profit > 0.02:  # 盈利2%后
            # 移动止损：保留1%利润
            return current_profit - 0.01
        
        # 其他情况不启用额外止损，使用固定止损（-8%）
        return None
    
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                           proposed_stake: float, min_stake: Optional[float], max_stake: float,
                           leverage: float, entry_tag: Optional[str], side: str,
                           **kwargs) -> float:
        # 激进仓位管理：放大仓位以追求高收益
        wallet = self.wallets.get_total_stake_amount()
        
        # 根据交易类型分配仓位（激进设置）
        if entry_tag == 'breakout':
            # 突破交易：10%仓位
            max_stake_amount = wallet * 0.10
        elif entry_tag == 'grid':
            # 网格交易：8%仓位
            max_stake_amount = wallet * 0.08
        elif entry_tag == 'trend':
            # 趋势交易：12%仓位（趋势明确时加大仓位）
            max_stake_amount = wallet * 0.12
        else:
            # 默认：8%仓位
            max_stake_amount = wallet * 0.08
        
        # 渐进加仓：网格交易中价格越低仓位越大
        if self.grid_progressive_position.value and entry_tag == 'grid':
            # 简化实现：如果价格在网格下部，增加仓位
            # 实际应基于当前价格在网格中的位置
            pass
        
        return min(proposed_stake, max_stake_amount)
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        return 1.0  # 现货交易
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                           time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                           side: str, **kwargs) -> bool:
        # 确认交易前检查
        self.trade_count_today += 1
        return True