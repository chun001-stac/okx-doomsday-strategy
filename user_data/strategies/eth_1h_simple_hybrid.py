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


class Eth1hSimpleHybrid(IStrategy):
    """
    ETH 1小时简化混合策略
    核心思想：趋势市追涨杀跌，震荡市高抛低吸
    简化判断逻辑，优化进出场条件
    """
    
    INTERFACE_VERSION = 3
    timeframe = '1h'
    
    # 止损止盈设置
    stoploss = -0.012  # 1.2% 止损
    minimal_roi = {
        "0": 0.048,    # 4.8% 止盈（盈亏比4:1）
        "20": 0.024,   # 20分钟后如果盈利2.4%则退出
        "40": 0.012,   # 40分钟后如果盈利1.2%则退出
        "80": 0        # 80分钟后保本退出
    }
    
    process_only_new_candles = True
    use_custom_stoploss = False
    startup_candle_count: int = 200
    
    # === 市场状态判断 ===
    # ADX趋势阈值
    adx_trend_threshold = IntParameter(18, 28, default=22, space="buy")
    
    # 布林带宽度阈值
    bb_width_trend_threshold = DecimalParameter(0.035, 0.065, default=0.05, decimals=3, space="buy")
    
    # 均线趋势判断
    ma_long_period = IntParameter(150, 250, default=200, space="buy")
    ma_short_period = IntParameter(10, 30, default=20, space="buy")
    
    # === 趋势策略参数 ===
    trend_rsi_period = IntParameter(7, 14, default=10, space="buy")
    trend_rsi_buy = IntParameter(45, 60, default=52, space="buy")  # 买入时RSI
    trend_rsi_sell = IntParameter(65, 80, default=72, space="sell")  # 卖出时RSI
    
    # === 网格策略参数 ===
    grid_rsi_period = IntParameter(7, 14, default=10, space="buy")
    grid_rsi_buy = IntParameter(30, 45, default=38, space="buy")  # 网格买入RSI
    grid_rsi_sell = IntParameter(55, 70, default=62, space="sell")  # 网格卖出RSI
    
    # === 通用参数 ===
    volume_ratio_min = DecimalParameter(1.1, 1.6, default=1.3, decimals=1, space="buy")
    min_atr_pct = DecimalParameter(0.4, 0.9, default=0.6, decimals=1, space="buy")
    
    # === 风险管理 ===
    max_position_pct = DecimalParameter(0.05, 0.12, default=0.07, decimals=2, space="buy")
    trend_position_pct = DecimalParameter(0.04, 0.10, default=0.06, decimals=2, space="buy")
    grid_position_pct = DecimalParameter(0.02, 0.06, default=0.03, decimals=2, space="buy")
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # === 基础指标 ===
        # 移动平均线
        dataframe['ma_long'] = dataframe['close'].rolling(window=self.ma_long_period.value).mean()
        dataframe['ma_short'] = dataframe['close'].rolling(window=self.ma_short_period.value).mean()
        dataframe['ma_fast'] = dataframe['close'].rolling(window=8).mean()
        
        # 均线趋势
        dataframe['ma_long_up'] = dataframe['ma_long'] > dataframe['ma_long'].shift(20)
        dataframe['ma_short_up'] = dataframe['ma_short'] > dataframe['ma_short'].shift(5)
        dataframe['ma_fast_up'] = dataframe['ma_fast'] > dataframe['ma_fast'].shift(2)
        
        # 价格位置
        dataframe['price_above_ma_long'] = dataframe['close'] > dataframe['ma_long']
        dataframe['price_above_ma_short'] = dataframe['close'] > dataframe['ma_short']
        
        # ADX趋势强度
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)
        
        # 布林带
        bb = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_middle'] = bb['middleband']
        dataframe['bb_upper'] = bb['upperband']
        dataframe['bb_lower'] = bb['lowerband']
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.trend_rsi_period.value)
        dataframe['grid_rsi'] = ta.RSI(dataframe, timeperiod=self.grid_rsi_period.value)
        
        # 成交量
        dataframe['volume_ma'] = dataframe['volume'].rolling(window=10).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']
        
        # ATR波动率
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close'] * 100
        
        # === 市场状态判断 ===
        # 趋势市条件：ADX高 + 布林带宽 + 均线向上
        trending_condition = (
            (dataframe['adx'] > self.adx_trend_threshold.value) &
            (dataframe['bb_width'] > self.bb_width_trend_threshold.value) &
            dataframe['ma_long_up'] &
            dataframe['price_above_ma_long']
        )
        
        # 震荡市条件：ADX低 + 布林带窄 + 价格在区间内
        ranging_condition = (
            (dataframe['adx'] < 20) &
            (dataframe['bb_width'] < 0.04) &
            (dataframe['close'] > dataframe['bb_lower'] * 1.02) &
            (dataframe['close'] < dataframe['bb_upper'] * 0.98)
        )
        
        dataframe['market_state'] = 'unknown'
        dataframe.loc[trending_condition, 'market_state'] = 'trending'
        dataframe.loc[ranging_condition, 'market_state'] = 'ranging'
        
        # === 趋势策略信号 ===
        # 趋势多头信号：均线多头 + RSI适中 + 成交量放大
        dataframe['trend_buy_signal'] = (
            trending_condition &
            dataframe['ma_fast_up'] &
            (dataframe['rsi'] > self.trend_rsi_buy.value) &
            (dataframe['rsi'] < self.trend_rsi_sell.value) &
            (dataframe['volume_ratio'] >= self.volume_ratio_min.value) &
            (dataframe['atr_pct'] >= self.min_atr_pct.value)
        )
        
        # === 网格策略信号 ===
        # 网格买入信号：价格接近布林带下轨 + RSI超卖
        dataframe['grid_buy_signal'] = (
            ranging_condition &
            (dataframe['close'] <= dataframe['bb_lower'] * 1.03) &  # 在下轨附近
            (dataframe['grid_rsi'] < self.grid_rsi_buy.value) &  # RSI超卖
            (dataframe['volume_ratio'] >= 1.0)  # 成交量不萎缩
        )
        
        # 网格卖出信号：价格接近布林带上轨 + RSI超买
        dataframe['grid_sell_signal'] = (
            ranging_condition &
            (dataframe['close'] >= dataframe['bb_upper'] * 0.97) &  # 在上轨附近
            (dataframe['grid_rsi'] > self.grid_rsi_sell.value)  # RSI超买
        )
        
        # 价格在网格中的位置（用于仓位管理）
        dataframe['price_to_lower'] = (dataframe['close'] - dataframe['bb_lower']) / (dataframe['bb_upper'] - dataframe['bb_lower'])
        dataframe['price_to_lower'] = dataframe['price_to_lower'].clip(0, 1)
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 趋势市：趋势买入
        trend_entry = (
            (dataframe['market_state'] == 'trending') &
            dataframe['trend_buy_signal'] &
            (dataframe['close'] > 0) &
            (dataframe['volume'] > 0)
        )
        
        # 震荡市：网格买入
        grid_entry = (
            (dataframe['market_state'] == 'ranging') &
            dataframe['grid_buy_signal'] &
            (dataframe['close'] > 0) &
            (dataframe['volume'] > 0)
        )
        
        dataframe.loc[trend_entry, 'enter_long'] = 1
        dataframe.loc[trend_entry, 'enter_tag'] = 'trend_buy'
        
        dataframe.loc[grid_entry, 'enter_long'] = 1
        dataframe.loc[grid_entry, 'enter_tag'] = 'grid_buy'
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 趋势策略出场：RSI超买或价格跌破短期均线
        trend_exit = (
            (dataframe['market_state'] == 'trending') &
            (
                (dataframe['rsi'] > self.trend_rsi_sell.value) |
                (dataframe['close'] < dataframe['ma_short'] * 0.985)
            )
        )
        
        # 网格策略出场：价格回到布林中轨或RSI回到中值
        grid_exit = (
            (dataframe['market_state'] == 'ranging') &
            (
                (dataframe['close'] >= dataframe['bb_middle'] * 1.01) |
                (dataframe['grid_rsi'] > 50)
            )
        )
        
        # 止损出场：跌破重要支撑
        stop_loss = (
            (dataframe['close'] < dataframe['bb_lower'] * 0.98)
        )
        
        dataframe.loc[trend_exit | grid_exit | stop_loss, 'exit_long'] = 1
        
        return dataframe
    
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                           proposed_stake: float, min_stake: Optional[float], max_stake: float,
                           leverage: float, entry_tag: Optional[str], side: str,
                           **kwargs) -> float:
        wallet = self.wallets.get_total_stake_amount()
        
        if entry_tag == 'trend_buy':
            max_stake_amount = wallet * self.trend_position_pct.value
        elif entry_tag == 'grid_buy':
            # 网格策略：价格越低仓位可以略大
            max_stake_amount = wallet * self.grid_position_pct.value
        else:
            max_stake_amount = wallet * self.max_position_pct.value
        
        return min(proposed_stake, max_stake_amount)
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        return 1.0