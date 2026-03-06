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


class Eth1hHyperoptOptimized(IStrategy):
    """
    ETH 1小时策略 - Hyperopt优化版
    基于Eth1hSimpleHybrid，使用Hyperopt找到的最优参数
    目标：月利润50%（激进参数设置）
    """
    
    INTERFACE_VERSION = 3
    timeframe = '1h'
    
    # Hyperopt优化后的止损止盈（非常激进）
    stoploss = -0.286  # 28.6% 止损（激进）
    minimal_roi = {
        "0": 0.263,    # 26.3% 止盈（激进）
        "402": 0.177,  # 402分钟后如果盈利17.7%则退出
        "674": 0.025,  # 674分钟后如果盈利2.5%则退出
        "1851": 0      # 1851分钟后保本退出
    }
    
    process_only_new_candles = True
    use_custom_stoploss = False
    startup_candle_count: int = 200
    
    # === 市场状态判断 ===
    # ADX趋势阈值（Hyperopt优化值）
    adx_trend_threshold = IntParameter(18, 28, default=27, space="buy")  # 优化后：27
    
    # 布林带宽度阈值（优化后）
    bb_width_trend_threshold = DecimalParameter(0.035, 0.065, default=0.045, decimals=3, space="buy")  # 优化后：0.045
    
    # 均线趋势判断（优化后）
    ma_long_period = IntParameter(150, 250, default=151, space="buy")  # 优化后：151
    ma_short_period = IntParameter(10, 30, default=15, space="buy")  # 优化后：15
    
    # === 趋势策略参数 ===
    trend_rsi_period = IntParameter(7, 14, default=9, space="buy")  # 优化后：9
    trend_rsi_buy = IntParameter(45, 60, default=51, space="buy")  # 优化后：51
    trend_rsi_sell = IntParameter(65, 80, default=67, space="sell")  # 优化后：67
    
    # === 网格策略参数（优化后） ===
    grid_rsi_period = IntParameter(7, 14, default=10, space="buy")  # 优化后：10
    grid_rsi_buy = IntParameter(30, 45, default=41, space="buy")  # 优化后：41
    grid_rsi_sell = IntParameter(55, 70, default=61, space="sell")  # 优化后：61
    
    # === 通用参数（优化后） ===
    volume_ratio_min = DecimalParameter(1.1, 1.6, default=1.2, decimals=1, space="buy")  # 优化后：1.2
    min_atr_pct = DecimalParameter(0.4, 0.9, default=0.8, decimals=1, space="buy")  # 优化后：0.8
    
    # === 风险管理（优化后） ===
    max_position_pct = DecimalParameter(0.05, 0.12, default=0.09, decimals=2, space="buy")  # 优化后：0.09
    trend_position_pct = DecimalParameter(0.04, 0.10, default=0.09, decimals=2, space="buy")  # 优化后：0.09
    grid_position_pct = DecimalParameter(0.02, 0.06, default=0.04, decimals=2, space="buy")  # 优化后：0.04
    
    # === 新增：交易频率优化 ===
    # 放宽市场状态判断，增加交易机会
    enable_more_trades = BooleanParameter(default=True, space="buy")
    
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
        
        # === 市场状态判断（放宽版） ===
        if self.enable_more_trades.value:
            # 放宽条件，增加交易机会
            trending_condition = (
                (dataframe['adx'] > self.adx_trend_threshold.value * 0.8) &  # 放宽ADX要求
                (dataframe['bb_width'] > self.bb_width_trend_threshold.value * 0.8) &  # 放宽布林带宽度
                (dataframe['price_above_ma_long'] | dataframe['ma_long_up'])  # 放宽均线要求
            )
            
            ranging_condition = (
                (dataframe['adx'] < 25) &  # 放宽震荡市判断
                (dataframe['bb_width'] < 0.05) &  # 放宽布林带宽度
                (dataframe['close'] > dataframe['bb_lower'] * 1.01) &  # 放宽价格区间
                (dataframe['close'] < dataframe['bb_upper'] * 0.99)
            )
        else:
            # 原条件
            trending_condition = (
                (dataframe['adx'] > self.adx_trend_threshold.value) &
                (dataframe['bb_width'] > self.bb_width_trend_threshold.value) &
                dataframe['ma_long_up'] &
                dataframe['price_above_ma_long']
            )
            
            ranging_condition = (
                (dataframe['adx'] < 20) &
                (dataframe['bb_width'] < 0.04) &
                (dataframe['close'] > dataframe['bb_lower'] * 1.02) &
                (dataframe['close'] < dataframe['bb_upper'] * 0.98)
            )
        
        dataframe['market_state'] = 'unknown'
        dataframe.loc[trending_condition, 'market_state'] = 'trending'
        dataframe.loc[ranging_condition, 'market_state'] = 'ranging'
        
        # === 新增：突破信号（增加交易机会） ===
        # 价格突破近期高点
        dataframe['high_20'] = dataframe['high'].rolling(window=20).max()
        dataframe['breakout_signal'] = (
            (dataframe['close'] > dataframe['high_20'].shift(1)) &
            (dataframe['volume_ratio'] > 1.5) &
            (dataframe['rsi'] > 40) &
            (dataframe['rsi'] < 70)
        )
        
        # === 趋势策略信号 ===
        dataframe['trend_buy_signal'] = (
            (dataframe['market_state'] == 'trending') &
            dataframe['ma_fast_up'] &
            (dataframe['rsi'] > self.trend_rsi_buy.value) &
            (dataframe['rsi'] < self.trend_rsi_sell.value) &
            (dataframe['volume_ratio'] >= self.volume_ratio_min.value) &
            (dataframe['atr_pct'] >= self.min_atr_pct.value)
        )
        
        # === 网格策略信号 ===
        dataframe['grid_buy_signal'] = (
            (dataframe['market_state'] == 'ranging') &
            (dataframe['close'] <= dataframe['bb_lower'] * 1.03) &
            (dataframe['grid_rsi'] < self.grid_rsi_buy.value) &
            (dataframe['volume_ratio'] >= 1.0)
        )
        
        dataframe['grid_sell_signal'] = (
            (dataframe['market_state'] == 'ranging') &
            (dataframe['close'] >= dataframe['bb_upper'] * 0.97) &
            (dataframe['grid_rsi'] > self.grid_rsi_sell.value)
        )
        
        # 价格在网格中的位置
        dataframe['price_to_lower'] = (dataframe['close'] - dataframe['bb_lower']) / (dataframe['bb_upper'] - dataframe['bb_lower'])
        dataframe['price_to_lower'] = dataframe['price_to_lower'].clip(0, 1)
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 趋势市：趋势买入
        trend_entry = (
            (dataframe['market_state'] == 'trending') &
            (dataframe['trend_buy_signal'] | dataframe['breakout_signal']) &  # 添加突破信号
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
        # 趋势策略出场
        trend_exit = (
            (dataframe['market_state'] == 'trending') &
            (
                (dataframe['rsi'] > self.trend_rsi_sell.value) |
                (dataframe['close'] < dataframe['ma_short'] * 0.97)  # 放宽止损
            )
        )
        
        # 网格策略出场
        grid_exit = (
            (dataframe['market_state'] == 'ranging') &
            (
                (dataframe['close'] >= dataframe['bb_middle'] * 1.02) |  # 放宽出场条件
                (dataframe['grid_rsi'] > 55)  # 放宽RSI条件
            )
        )
        
        # 激进止损：只有大幅下跌才止损
        stop_loss = (
            (dataframe['close'] < dataframe['bb_lower'] * 0.95)  # 放宽止损
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
            max_stake_amount = wallet * self.grid_position_pct.value
        else:
            max_stake_amount = wallet * self.max_position_pct.value
        
        return min(proposed_stake, max_stake_amount)
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        return 1.0