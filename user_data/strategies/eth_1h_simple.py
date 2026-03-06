# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these imports ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Union

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta


class Eth1hSimple(IStrategy):
    """
    简化版ETH 1小时策略
    只使用核心条件：MA多头 + RSI适中 + 成交量放大
    严格控制风险
    """
    
    INTERFACE_VERSION = 3
    timeframe = '1h'
    
    # 严格止损止盈
    stoploss = -0.015  # 1.5% 止损
    minimal_roi = {
        "0": 0.045,    # 4.5% 止盈（盈亏比3:1）
        "30": 0.02,    # 30分钟后如果盈利2%则退出
        "60": 0.01,    # 60分钟后如果盈利1%则退出
        "120": 0       # 120分钟后保本退出
    }
    
    process_only_new_candles = True
    use_custom_stoploss = False  # 使用固定止损
    startup_candle_count: int = 100
    
    # 参数
    ma_short = IntParameter(5, 9, default=7, space="buy")
    ma_long = IntParameter(10, 20, default=14, space="buy")
    rsi_period = IntParameter(7, 14, default=10, space="buy")
    rsi_min = IntParameter(45, 55, default=50, space="buy")
    rsi_max = IntParameter(60, 70, default=65, space="buy")
    volume_ratio_min = DecimalParameter(1.1, 1.5, default=1.3, decimals=1, space="buy")
    
    # 最大仓位
    max_position_pct = DecimalParameter(0.05, 0.15, default=0.08, decimals=2, space="buy")
    
    # 交易间隔（小时）
    min_trade_interval = IntParameter(2, 6, default=4, space="buy")
    
    # 状态变量
    last_trade_time = None
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 移动平均线
        dataframe['ma_fast'] = dataframe['close'].rolling(window=self.ma_short.value).mean()
        dataframe['ma_slow'] = dataframe['close'].rolling(window=self.ma_long.value).mean()
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        
        # 成交量均线
        dataframe['volume_ma'] = dataframe['volume'].rolling(window=10).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']
        
        # ATR（用于过滤低波动市场）
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close'] * 100
        
        # 价格位置
        dataframe['price_above_ma'] = dataframe['close'] > dataframe['ma_slow']
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 核心条件
        ma_condition = dataframe['ma_fast'] > dataframe['ma_slow']
        rsi_condition = (dataframe['rsi'] >= self.rsi_min.value) & (dataframe['rsi'] <= self.rsi_max.value)
        volume_condition = dataframe['volume_ratio'] >= self.volume_ratio_min.value
        atr_condition = dataframe['atr_pct'] > 0.5  # 过滤低波动市场
        price_condition = dataframe['price_above_ma']
        
        # 综合信号
        dataframe.loc[
            (
                ma_condition &
                rsi_condition &
                volume_condition &
                atr_condition &
                price_condition &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
        
        dataframe.loc[dataframe['enter_long'] == 1, 'enter_tag'] = 'eth_simple'
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 使用固定止损止盈，这里不设置额外退出条件
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