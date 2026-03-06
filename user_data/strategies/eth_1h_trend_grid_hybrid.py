# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these imports ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Union

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, BooleanParameter
import talib.abstract as ta


class Eth1hTrendGridHybrid(IStrategy):
    """
    ETH 1小时混合策略：趋势跟踪 + 网格交易
    根据市场状态动态切换策略：
    - 趋势市：趋势跟踪（做多/做空）
    - 震荡市：网格交易（高抛低吸）
    """
    
    INTERFACE_VERSION = 3
    timeframe = '1h'
    
    # 双重止损止盈设置
    # 趋势策略
    stoploss = -0.02  # 2% 止损（趋势策略）
    minimal_roi = {
        "0": 0.06,     # 6% 止盈（趋势策略）
        "30": 0.03,
        "60": 0.015,
        "120": 0
    }
    
    # 网格策略参数
    grid_levels = IntParameter(3, 8, default=5, space="buy")  # 网格层数
    grid_spacing_pct = DecimalParameter(0.01, 0.03, default=0.015, decimals=3, space="buy")  # 网格间距
    grid_position_pct = DecimalParameter(0.03, 0.10, default=0.05, decimals=2, space="buy")  # 每层仓位
    
    process_only_new_candles = True
    use_custom_stoploss = True
    startup_candle_count: int = 250
    
    # === 市场状态判断参数 ===
    # ADX阈值：高于此为趋势市，低于此为震荡市
    adx_trend_threshold = IntParameter(20, 30, default=25, space="buy")
    adx_period = IntParameter(10, 20, default=14, space="buy")
    
    # 布林带宽度阈值：窄为震荡市，宽为趋势市
    bb_width_trend_threshold = DecimalParameter(0.04, 0.08, default=0.06, decimals=3, space="buy")
    bb_period = IntParameter(18, 22, default=20, space="buy")
    bb_std = DecimalParameter(1.8, 2.2, default=2.0, decimals=1, space="buy")
    
    # ATR相对阈值
    atr_trend_threshold = DecimalParameter(0.8, 1.2, default=1.0, decimals=2, space="buy")
    atr_period = IntParameter(10, 20, default=14, space="buy")
    
    # 均线趋势判断
    ma_trend_period = IntParameter(180, 220, default=200, space="buy")
    ma_signal_period = IntParameter(10, 30, default=20, space="buy")
    
    # === 趋势策略参数 ===
    trend_ma_fast = IntParameter(5, 10, default=7, space="buy")
    trend_ma_slow = IntParameter(15, 30, default=20, space="buy")
    trend_rsi_period = IntParameter(7, 14, default=10, space="buy")
    trend_rsi_overbought = IntParameter(65, 75, default=70, space="sell")
    trend_rsi_oversold = IntParameter(25, 35, default=30, space="buy")
    
    # === 网格策略参数 ===
    grid_rsi_period = IntParameter(7, 14, default=10, space="buy")
    grid_rsi_upper = IntParameter(65, 75, default=70, space="sell")
    grid_rsi_lower = IntParameter(25, 35, default=30, space="buy")
    
    # === 风险管理 ===
    max_position_pct = DecimalParameter(0.05, 0.15, default=0.08, decimals=2, space="buy")
    trend_position_pct = DecimalParameter(0.03, 0.08, default=0.05, decimals=2, space="buy")
    grid_position_pct = DecimalParameter(0.01, 0.04, default=0.02, decimals=2, space="buy")
    
    # 状态变量
    market_state = "unknown"  # "trending", "ranging", "unknown"
    current_grid_levels = []
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # === 市场状态判断指标 ===
        # ADX - 趋势强度
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)
        
        # 布林带宽度
        bb = ta.BBANDS(dataframe, timeperiod=self.bb_period.value, nbdevup=self.bb_std.value, nbdevdn=self.bb_std.value)
        dataframe['bb_middle'] = bb['middleband']
        dataframe['bb_upper'] = bb['upperband']
        dataframe['bb_lower'] = bb['lowerband']
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']
        
        # ATR相对值（相对于N周期平均）
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period.value)
        dataframe['atr_ma'] = dataframe['atr'].rolling(window=20).mean()
        dataframe['atr_ratio'] = dataframe['atr'] / dataframe['atr_ma']
        
        # 均线趋势
        dataframe['ma_trend'] = dataframe['close'].rolling(window=self.ma_trend_period.value).mean()
        dataframe['ma_signal'] = dataframe['close'].rolling(window=self.ma_signal_period.value).mean()
        dataframe['ma_trend_up'] = dataframe['ma_trend'] > dataframe['ma_trend'].shift(20)
        dataframe['ma_signal_up'] = dataframe['ma_signal'] > dataframe['ma_signal'].shift(5)
        
        # 趋势方向
        dataframe['price_above_ma_trend'] = dataframe['close'] > dataframe['ma_trend']
        dataframe['price_above_ma_signal'] = dataframe['close'] > dataframe['ma_signal']
        
        # === 市场状态判断 ===
        # 条件1：ADX > 阈值 且 布林带宽 > 阈值 → 趋势市
        adx_trend = dataframe['adx'] > self.adx_trend_threshold.value
        bb_width_trend = dataframe['bb_width'] > self.bb_width_trend_threshold.value
        atr_trend = dataframe['atr_ratio'] > self.atr_trend_threshold.value
        
        # 条件2：均线明确排列 → 趋势市
        ma_alignment = (dataframe['ma_signal'] > dataframe['ma_trend']) & dataframe['ma_trend_up']
        
        # 综合判断
        dataframe['is_trending'] = (adx_trend & bb_width_trend) | (atr_trend & ma_alignment)
        dataframe['is_ranging'] = (~dataframe['is_trending']) & (dataframe['adx'] < 20) & (dataframe['bb_width'] < 0.05)
        
        # 默认状态
        dataframe['market_state'] = 'unknown'
        dataframe.loc[dataframe['is_trending'], 'market_state'] = 'trending'
        dataframe.loc[dataframe['is_ranging'], 'market_state'] = 'ranging'
        
        # === 趋势策略指标 ===
        dataframe['trend_ma_fast'] = dataframe['close'].rolling(window=self.trend_ma_fast.value).mean()
        dataframe['trend_ma_slow'] = dataframe['close'].rolling(window=self.trend_ma_slow.value).mean()
        dataframe['trend_ma_bullish'] = dataframe['trend_ma_fast'] > dataframe['trend_ma_slow']
        dataframe['trend_ma_bearish'] = dataframe['trend_ma_fast'] < dataframe['trend_ma_slow']
        
        dataframe['trend_rsi'] = ta.RSI(dataframe, timeperiod=self.trend_rsi_period.value)
        
        # 趋势进场信号
        dataframe['trend_long_signal'] = (
            dataframe['trend_ma_bullish'] &
            (dataframe['trend_rsi'] > self.trend_rsi_oversold.value) &
            (dataframe['trend_rsi'] < self.trend_rsi_overbought.value) &
            dataframe['price_above_ma_signal']
        )
        
        dataframe['trend_short_signal'] = (
            dataframe['trend_ma_bearish'] &
            (dataframe['trend_rsi'] > self.trend_rsi_oversold.value) &
            (dataframe['trend_rsi'] < self.trend_rsi_overbought.value) &
            (~dataframe['price_above_ma_signal'])
        )
        
        # === 网格策略指标 ===
        dataframe['grid_rsi'] = ta.RSI(dataframe, timeperiod=self.grid_rsi_period.value)
        
        # 计算网格水平（基于布林带）
        dataframe['grid_upper'] = dataframe['bb_upper'] * 0.98  # 上轨略下移
        dataframe['grid_lower'] = dataframe['bb_lower'] * 1.02  # 下轨略上移
        dataframe['grid_middle'] = dataframe['bb_middle']
        
        # 网格进场信号
        dataframe['grid_buy_signal'] = (
            (dataframe['close'] <= dataframe['grid_lower']) &
            (dataframe['grid_rsi'] < self.grid_rsi_lower.value)
        )
        
        dataframe['grid_sell_signal'] = (
            (dataframe['close'] >= dataframe['grid_upper']) &
            (dataframe['grid_rsi'] > self.grid_rsi_upper.value)
        )
        
        # 当前价格在网格中的位置
        dataframe['grid_position'] = (dataframe['close'] - dataframe['grid_lower']) / (dataframe['grid_upper'] - dataframe['grid_lower'])
        dataframe['grid_position'] = dataframe['grid_position'].clip(0, 1)  # 限制在0-1之间
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 根据市场状态选择策略
        
        # 趋势市：趋势跟踪策略
        trend_long_condition = (
            (dataframe['market_state'] == 'trending') &
            dataframe['trend_long_signal'] &
            dataframe['price_above_ma_trend']  # 确保在长期趋势之上
        )
        
        trend_short_condition = (
            (dataframe['market_state'] == 'trending') &
            dataframe['trend_short_signal'] &
            (~dataframe['price_above_ma_trend'])  # 确保在长期趋势之下
        )
        
        # 震荡市：网格策略
        grid_buy_condition = (
            (dataframe['market_state'] == 'ranging') &
            dataframe['grid_buy_signal'] &
            (dataframe['grid_position'] < 0.3)  # 在下部区域
        )
        
        grid_sell_condition = (
            (dataframe['market_state'] == 'ranging') &
            dataframe['grid_sell_signal'] &
            (dataframe['grid_position'] > 0.7)  # 在上部区域
        )
        
        # 设置进场信号
        dataframe.loc[trend_long_condition, 'enter_long'] = 1
        dataframe.loc[trend_long_condition, 'enter_tag'] = 'trend_long'
        
        # 注意：Freqtrade默认只支持做多，如果需要做空需要特殊配置
        # 这里先只实现做多，做空逻辑可以后期添加
        
        dataframe.loc[grid_buy_condition, 'enter_long'] = 1
        dataframe.loc[grid_buy_condition, 'enter_tag'] = 'grid_buy'
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 趋势策略出场
        trend_exit_long = (
            (dataframe['market_state'] == 'trending') &
            (
                (dataframe['trend_rsi'] > self.trend_rsi_overbought.value) |
                (~dataframe['trend_ma_bullish']) |
                (~dataframe['price_above_ma_signal'])
            )
        )
        
        # 网格策略出场（获利了结）
        grid_exit_long = (
            (dataframe['market_state'] == 'ranging') &
            (
                (dataframe['grid_rsi'] > self.grid_rsi_upper.value) |
                (dataframe['close'] >= dataframe['grid_middle'] * 1.02)  # 回到中轨上方
            )
        )
        
        # 止损出场（通用）
        stop_loss = (
            (dataframe['close'] < dataframe['bb_lower'] * 0.98)  # 跌破下轨
        )
        
        dataframe.loc[trend_exit_long | grid_exit_long | stop_loss, 'exit_long'] = 1
        
        return dataframe
    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> Optional[float]:
        # 根据交易标签设置不同的止损
        if trade.enter_tag == 'trend_long':
            # 趋势策略：宽松止损
            if current_profit > 0.03:  # 盈利3%后启动移动止损
                return current_profit - 0.015  # 移动止损1.5%
            return None  # 使用固定止损
        
        elif trade.enter_tag == 'grid_buy':
            # 网格策略：严格止损
            if current_profit > 0.01:  # 盈利1%后保本
                return -0.001  # 几乎保本
            return None  # 使用固定止损
        
        return None
    
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                           proposed_stake: float, min_stake: Optional[float], max_stake: float,
                           leverage: float, entry_tag: Optional[str], side: str,
                           **kwargs) -> float:
        # 根据策略类型调整仓位
        wallet = self.wallets.get_total_stake_amount()
        
        if entry_tag == 'trend_long':
            max_stake_amount = wallet * self.trend_position_pct.value
        elif entry_tag == 'grid_buy':
            max_stake_amount = wallet * self.grid_position_pct.value
        else:
            max_stake_amount = wallet * self.max_position_pct.value
        
        return min(proposed_stake, max_stake_amount)
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        return 1.0  # 现货交易
    
    def informative_pairs(self):
        # 可以添加其他交易对作为市场状态参考
        return []