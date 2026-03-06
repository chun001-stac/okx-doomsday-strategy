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


class Eth1hTrendFilter(IStrategy):
    """
    趋势过滤版ETH 1小时策略
    只在上张趋势中交易（价格>200MA）
    严格控制风险，减少交易频率
    """
    
    INTERFACE_VERSION = 3
    timeframe = '1h'
    
    # 严格止损止盈
    stoploss = -0.012  # 1.2% 止损
    minimal_roi = {
        "0": 0.036,    # 3.6% 止盈（盈亏比3:1）
        "20": 0.018,   # 20分钟后如果盈利1.8%则退出
        "40": 0.009,   # 40分钟后如果盈利0.9%则退出
        "80": 0        # 80分钟后保本退出
    }
    
    process_only_new_candles = True
    use_custom_stoploss = False
    startup_candle_count: int = 250  # 需要计算200MA
    
    # 趋势参数
    trend_ma_period = IntParameter(150, 250, default=200, space="buy")
    
    # 进场参数
    ma_fast_period = IntParameter(5, 12, default=8, space="buy")
    ma_slow_period = IntParameter(15, 30, default=20, space="buy")
    rsi_period = IntParameter(7, 14, default=10, space="buy")
    rsi_min = IntParameter(48, 58, default=52, space="buy")
    rsi_max = IntParameter(62, 72, default=67, space="buy")
    volume_ratio_min = DecimalParameter(1.15, 1.6, default=1.35, decimals=1, space="buy")
    
    # 波动率过滤
    min_atr_pct = DecimalParameter(0.4, 1.0, default=0.6, decimals=1, space="buy")
    
    # 风险管理
    max_position_pct = DecimalParameter(0.04, 0.10, default=0.06, decimals=2, space="buy")
    
    # 交易冷却
    trade_cooldown = IntParameter(3, 8, default=5, space="buy")  # 小时
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 趋势均线
        dataframe['ma_trend'] = dataframe['close'].rolling(window=self.trend_ma_period.value).mean()
        dataframe['trend_up'] = dataframe['close'] > dataframe['ma_trend']
        
        # 快慢均线
        dataframe['ma_fast'] = dataframe['close'].rolling(window=self.ma_fast_period.value).mean()
        dataframe['ma_slow'] = dataframe['close'].rolling(window=self.ma_slow_period.value).mean()
        dataframe['ma_bullish'] = dataframe['ma_fast'] > dataframe['ma_slow']
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        
        # 成交量
        dataframe['volume_ma'] = dataframe['volume'].rolling(window=10).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']
        
        # ATR波动率
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close'] * 100
        
        # 价格位置
        dataframe['price_above_slow'] = dataframe['close'] > dataframe['ma_slow']
        
        # 信号强度计算
        conditions = [
            dataframe['trend_up'],           # 趋势向上
            dataframe['ma_bullish'],         # 均线多头
            (dataframe['rsi'] >= self.rsi_min.value) & (dataframe['rsi'] <= self.rsi_max.value),  # RSI适中
            dataframe['volume_ratio'] >= self.volume_ratio_min.value,  # 成交量放大
            dataframe['price_above_slow'],   # 价格在慢线上方
            dataframe['atr_pct'] >= self.min_atr_pct.value  # 足够波动
        ]
        
        dataframe['signal_strength'] = sum(conditions)
        dataframe['max_conditions'] = len(conditions)
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 要求满足所有条件
        dataframe.loc[
            (
                (dataframe['signal_strength'] == dataframe['max_conditions']) &
                (dataframe['volume'] > 0) &
                (dataframe['close'] > 0)
            ),
            'enter_long'] = 1
        
        dataframe.loc[dataframe['enter_long'] == 1, 'enter_tag'] = 'trend_filter'
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI过高时退出
        dataframe.loc[
            (
                (dataframe['rsi'] > 75) |
                (dataframe['close'] < dataframe['ma_slow'] * 0.985)  # 跌破慢线1.5%
            ),
            'exit_long'] = 1
        
        return dataframe
    
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                           proposed_stake: float, min_stake: Optional[float], max_stake: float,
                           leverage: float, entry_tag: Optional[str], side: str,
                           **kwargs) -> float:
        # 控制仓位大小
        wallet = self.wallets.get_total_stake_amount()
        max_stake_amount = wallet * self.max_position_pct.value
        return min(proposed_stake, max_stake_amount)
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        return 1.0