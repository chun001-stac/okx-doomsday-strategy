# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these imports ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Union

from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IStrategy, IntParameter, RealParameter)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
from functools import reduce
import pandas_ta as pta


class Eth1hV7431Opt1(IStrategy):
    """
    ETH/USDT 1小时策略 V74.31 优化版1
    放宽条件，调整参数
    """
    
    INTERFACE_VERSION = 3
    timeframe = '1h'
    
    # 固定止损止盈（简化版，后续可改为动态）
    stoploss = -0.025  # 2.5% 止损
    minimal_roi = {
        "0": 0.075,   # 7.5% 止盈
        "30": 0.03,   # 30分钟后如果盈利3%则退出
        "60": 0.01,   # 60分钟后如果盈利1%则退出
        "120": 0      # 120分钟后保本退出
    }
    
    process_only_new_candles = True
    use_custom_stoploss = True
    startup_candle_count: int = 300
    
    # 条件开关 - 全部开启
    use_ma = BooleanParameter(default=True, space="buy")
    use_rsi = BooleanParameter(default=True, space="buy")
    use_volume = BooleanParameter(default=True, space="buy")
    use_momentum = BooleanParameter(default=True, space="buy")
    use_price_position = BooleanParameter(default=True, space="buy")
    use_long_trend = BooleanParameter(default=True, space="buy")
    use_adx = BooleanParameter(default=True, space="buy")
    use_bb = BooleanParameter(default=True, space="buy")
    use_cci = BooleanParameter(default=True, space="buy")
    use_ma_slope = BooleanParameter(default=True, space="buy")
    
    # 优化参数 - 放宽条件
    min_conditions = IntParameter(4, 7, default=5, space="buy")  # 从6降到5
    
    # MA参数
    ma_short = IntParameter(3, 8, default=5, space="buy")
    ma_long = IntParameter(8, 15, default=10, space="buy")
    ma_trend = IntParameter(15, 30, default=20, space="buy")
    long_ma_period = IntParameter(150, 250, default=200, space="buy")
    
    # RSI参数 - 放宽范围
    rsi_period = IntParameter(5, 14, default=7, space="buy")
    rsi_min = IntParameter(45, 55, default=50, space="buy")  # 从60降到50
    rsi_max = IntParameter(65, 75, default=70, space="buy")  # 从75降到70
    
    # 成交量参数 - 降低要求
    volume_ma = IntParameter(3, 10, default=5, space="buy")
    min_volume_ratio = DecimalParameter(1.0, 1.5, default=1.2, decimals=1, space="buy")  # 从1.4降到1.2
    
    # 动量参数
    momentum_period = IntParameter(2, 5, default=3, space="buy")
    min_momentum = DecimalParameter(0.1, 0.8, default=0.3, decimals=1, space="buy")  # 从0.5降到0.3
    
    # ADX参数 - 降低阈值
    adx_period = IntParameter(10, 20, default=14, space="buy")
    min_adx = IntParameter(18, 25, default=20, space="buy")  # 从23降到20
    
    # 布林带参数
    bb_period = IntParameter(15, 25, default=20, space="buy")
    bb_std = DecimalParameter(1.5, 2.5, default=2.0, decimals=1, space="buy")
    bb_width_threshold = DecimalParameter(0.02, 0.08, default=0.05, decimals=3, space="buy")  # 从0.07降到0.05
    
    # CCI参数
    cci_period = IntParameter(14, 26, default=20, space="buy")
    cci_threshold = IntParameter(-10, 10, default=0, space="buy")
    
    # ATR参数 - 调整倍数
    atr_period = IntParameter(10, 20, default=14, space="buy")
    atr_multiplier_stop = DecimalParameter(1.5, 3.0, default=2.5, decimals=1, space="sell")  # 从3.0降到2.5
    atr_multiplier_profit = DecimalParameter(5.0, 10.0, default=7.5, decimals=1, space="sell")  # 从9.0降到7.5
    
    # 移动止损参数
    use_trailing = BooleanParameter(default=True, space="sell")
    trail_activation = DecimalParameter(0.005, 0.02, default=0.01, decimals=3, space="sell")  # 激活阈值1%
    trail_distance = DecimalParameter(0.005, 0.015, default=0.01, decimals=3, space="sell")  # 距离1%
    
    # 风险管理
    max_position_size = DecimalParameter(0.05, 0.15, default=0.08, decimals=2, space="buy")  # 最大仓位8%
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 基础价格数据
        dataframe['close'] = dataframe['close']
        dataframe['high'] = dataframe['high']
        dataframe['low'] = dataframe['low']
        dataframe['volume'] = dataframe['volume']
        
        # 移动平均线
        dataframe['ma5'] = ta.SMA(dataframe, timeperiod=self.ma_short.value)
        dataframe['ma10'] = ta.SMA(dataframe, timeperiod=self.ma_long.value)
        dataframe['ma20'] = ta.SMA(dataframe, timeperiod=self.ma_trend.value)
        dataframe['ma200'] = ta.SMA(dataframe, timeperiod=self.long_ma_period.value)
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        
        # 成交量均线
        dataframe['volume_ma'] = ta.SMA(dataframe['volume'], timeperiod=self.volume_ma.value)
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']
        
        # 动量
        dataframe['momentum'] = (dataframe['close'] - dataframe['close'].shift(self.momentum_period.value)) / dataframe['close'].shift(self.momentum_period.value) * 100
        
        # ATR
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period.value)
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close'] * 100
        
        # ADX
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)
        
        # 布林带
        bb = ta.BBANDS(dataframe, timeperiod=self.bb_period.value, nbdevup=self.bb_std.value, nbdevdn=self.bb_std.value)
        dataframe['bb_middle'] = bb['middleband']
        dataframe['bb_upper'] = bb['upperband']
        dataframe['bb_lower'] = bb['lowerband']
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']
        
        # CCI
        dataframe['cci'] = ta.CCI(dataframe, timeperiod=self.cci_period.value)
        
        # MA斜率
        dataframe['ma5_slope'] = dataframe['ma5'] > dataframe['ma5'].shift(1)
        
        # 计算条件
        conditions = {}
        
        # 1. MA多头
        if self.use_ma.value:
            conditions['ma_trend'] = (dataframe['ma5'] > dataframe['ma10']) & (dataframe['ma10'] > dataframe['ma20'])
        
        # 2. RSI
        if self.use_rsi.value:
            conditions['rsi_ok'] = (dataframe['rsi'] >= self.rsi_min.value) & (dataframe['rsi'] <= self.rsi_max.value)
        
        # 3. 成交量
        if self.use_volume.value:
            conditions['volume_ok'] = dataframe['volume_ratio'] >= self.min_volume_ratio.value
        
        # 4. 动量
        if self.use_momentum.value:
            conditions['momentum_ok'] = dataframe['momentum'] > self.min_momentum.value
        
        # 5. 价格>MA20
        if self.use_price_position.value:
            conditions['price_above_ma20'] = dataframe['close'] > dataframe['ma20']
        
        # 6. 价格>MA200
        if self.use_long_trend.value:
            conditions['price_above_ma200'] = dataframe['close'] > dataframe['ma200']
        
        # 7. ADX
        if self.use_adx.value:
            conditions['adx_ok'] = dataframe['adx'] > self.min_adx.value
        
        # 8. 布林带宽度
        if self.use_bb.value:
            conditions['bb_width_ok'] = dataframe['bb_width'] > self.bb_width_threshold.value
        
        # 9. CCI
        if self.use_cci.value:
            conditions['cci_ok'] = dataframe['cci'] > self.cci_threshold.value
        
        # 10. MA斜率
        if self.use_ma_slope.value:
            conditions['ma_slope_ok'] = dataframe['ma5_slope']
        
        # 计算满足条件数
        condition_columns = list(conditions.keys())
        if condition_columns:
            condition_df = pd.concat([conditions[col] for col in condition_columns], axis=1)
            condition_df.columns = condition_columns
            dataframe['conditions_met'] = condition_df.sum(axis=1)
            dataframe['total_conditions'] = len(condition_columns)
        else:
            dataframe['conditions_met'] = 0
            dataframe['total_conditions'] = 0
        
        # 进场信号
        dataframe['entry_signal'] = dataframe['conditions_met'] >= self.min_conditions.value
        
        # 添加过滤条件：ATR不能太小
        dataframe['atr_ok'] = dataframe['atr_pct'] > 0.3  # ATR至少0.3%
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                dataframe['entry_signal'] &
                dataframe['atr_ok'] &
                (dataframe['volume'] > 0) &
                (dataframe['conditions_met'] >= self.min_conditions.value) &
                (dataframe['close'] > 0)
            ),
            'enter_long'] = 1
        
        dataframe.loc[dataframe['enter_long'] == 1, 'enter_tag'] = 'eth_1h_opt1'
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 主要依赖止损止盈，这里设置简单的退出条件
        dataframe.loc[
            (
                (dataframe['rsi'] > 80) |  # RSI过高
                (dataframe['close'] < dataframe['ma20'] * 0.98)  # 跌破MA20 2%
            ),
            'exit_long'] = 1
        
        return dataframe
    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> Optional[float]:
        # 移动止损逻辑
        if self.use_trailing.value and current_profit > self.trail_activation.value:
            # 计算移动止损水平
            trail_stop = current_profit - self.trail_distance.value
            return trail_stop
        
        return None
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        return 1.0  # 现货