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


class Eth1hTrendParamOpt2(IStrategy):
    """
    ETH 1小时策略 - 趋势过滤 + 参数优化版2
    进一步放宽条件，调整止损止盈，添加价格位置过滤
    """
    
    INTERFACE_VERSION = 3
    timeframe = '1h'
    
    # 调整止损止盈比例
    stoploss = -0.015  # 1.5% 止损
    minimal_roi = {
        "0": 0.045,    # 4.5% 止盈（盈亏比3:1）
        "20": 0.0225,  # 20分钟后如果盈利2.25%则退出
        "40": 0.01125, # 40分钟后如果盈利1.125%则退出
        "80": 0        # 80分钟后保本退出
    }
    
    process_only_new_candles = True
    use_custom_stoploss = False
    startup_candle_count: int = 250
    
    # === 趋势参数 ===
    trend_ma_period = IntParameter(180, 220, default=200, space="buy")
    
    # === 条件参数（进一步放宽） ===
    # MA参数
    ma_short = IntParameter(4, 7, default=5, space="buy")
    ma_long = IntParameter(8, 14, default=10, space="buy")
    ma_trend_period = IntParameter(15, 22, default=18, space="buy")
    
    # RSI参数（进一步放宽）
    rsi_period = IntParameter(6, 10, default=8, space="buy")
    rsi_min = IntParameter(48, 55, default=51, space="buy")  # 进一步降低
    rsi_max = IntParameter(65, 72, default=68, space="buy")  # 进一步降低
    
    # 成交量参数（进一步放宽）
    volume_ma_period = IntParameter(4, 7, default=5, space="buy")
    volume_ratio_min = DecimalParameter(1.05, 1.4, default=1.15, decimals=2, space="buy")  # 进一步降低
    
    # 动量参数
    momentum_period = IntParameter(2, 4, default=3, space="buy")
    momentum_min = DecimalParameter(0.15, 0.5, default=0.25, decimals=2, space="buy")  # 进一步降低
    
    # ADX参数（进一步放宽）
    adx_period = IntParameter(12, 16, default=14, space="buy")
    adx_min = IntParameter(16, 22, default=19, space="buy")  # 进一步降低
    
    # 布林带参数
    bb_period = IntParameter(18, 22, default=20, space="buy")
    bb_std = DecimalParameter(1.8, 2.2, default=2.0, decimals=1, space="buy")
    bb_width_min = DecimalParameter(0.03, 0.07, default=0.05, decimals=3, space="buy")  # 进一步降低
    
    # CCI参数
    cci_period = IntParameter(18, 22, default=20, space="buy")
    cci_threshold = IntParameter(-10, 5, default=-2, space="buy")  # 放宽
    
    # === 条件门槛 ===
    min_conditions = IntParameter(3, 5, default=4, space="buy")  # 进一步降低到4
    
    # === 价格位置过滤 ===
    price_position_lookback = IntParameter(10, 30, default=20, space="buy")
    price_position_min = DecimalParameter(0.85, 0.95, default=0.90, decimals=2, space="buy")
    
    # === 风险管理 ===
    max_position_pct = DecimalParameter(0.05, 0.12, default=0.08, decimals=2, space="buy")
    trade_cooldown = IntParameter(3, 6, default=4, space="buy")
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 趋势均线
        dataframe['ma_trend'] = dataframe['close'].rolling(window=self.trend_ma_period.value).mean()
        dataframe['ma_trend_up'] = dataframe['ma_trend'] > dataframe['ma_trend'].shift(20)
        dataframe['trend_bullish'] = (dataframe['close'] > dataframe['ma_trend']) & dataframe['ma_trend_up']
        
        # 快慢均线
        dataframe['ma_fast'] = dataframe['close'].rolling(window=self.ma_short.value).mean()
        dataframe['ma_mid'] = dataframe['close'].rolling(window=self.ma_long.value).mean()
        dataframe['ma_slow'] = dataframe['close'].rolling(window=self.ma_trend_period.value).mean()
        dataframe['ma_bullish'] = (dataframe['ma_fast'] > dataframe['ma_mid']) & (dataframe['ma_mid'] > dataframe['ma_slow'])
        
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        
        # 成交量
        dataframe['volume_ma'] = dataframe['volume'].rolling(window=self.volume_ma_period.value).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_ma']
        
        # 动量
        dataframe['momentum'] = (dataframe['close'] - dataframe['close'].shift(self.momentum_period.value)) / dataframe['close'].shift(self.momentum_period.value) * 100
        
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
        dataframe['ma_slope'] = dataframe['ma_fast'] > dataframe['ma_fast'].shift(1)
        
        # 价格位置
        dataframe['price_above_ma_slow'] = dataframe['close'] > dataframe['ma_slow']
        dataframe['price_above_ma_trend'] = dataframe['close'] > dataframe['ma_trend']
        
        # 价格相对位置（相对于近期高点）
        dataframe['high_20'] = dataframe['high'].rolling(window=self.price_position_lookback.value).max()
        dataframe['price_position'] = dataframe['close'] / dataframe['high_20']
        dataframe['price_near_high'] = dataframe['price_position'] >= self.price_position_min.value
        
        # ATR
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close'] * 100
        
        # 计算10个条件
        conditions = []
        
        # 1. MA多头排列
        conditions.append(dataframe['ma_bullish'])
        
        # 2. RSI在范围内
        conditions.append((dataframe['rsi'] >= self.rsi_min.value) & (dataframe['rsi'] <= self.rsi_max.value))
        
        # 3. 成交量放大
        conditions.append(dataframe['volume_ratio'] >= self.volume_ratio_min.value)
        
        # 4. 正动量
        conditions.append(dataframe['momentum'] > self.momentum_min.value)
        
        # 5. 价格在慢线之上
        conditions.append(dataframe['price_above_ma_slow'])
        
        # 6. 价格在趋势线之上
        conditions.append(dataframe['price_above_ma_trend'])
        
        # 7. ADX大于阈值
        conditions.append(dataframe['adx'] > self.adx_min.value)
        
        # 8. 布林带宽度足够
        conditions.append(dataframe['bb_width'] > self.bb_width_min.value)
        
        # 9. CCI大于阈值
        conditions.append(dataframe['cci'] > self.cci_threshold.value)
        
        # 10. MA斜率向上
        conditions.append(dataframe['ma_slope'])
        
        # 计算满足条件数
        if conditions:
            cond_df = pd.concat(conditions, axis=1)
            cond_df.columns = [f'cond_{i}' for i in range(len(conditions))]
            dataframe['conditions_met'] = cond_df.sum(axis=1)
            dataframe['total_conditions'] = len(conditions)
        else:
            dataframe['conditions_met'] = 0
            dataframe['total_conditions'] = 0
        
        dataframe['signal_strength'] = dataframe['conditions_met'] / dataframe['total_conditions']
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 进场条件：趋势向上 + 满足足够条件 + 价格接近近期高点 + 波动率足够
        dataframe.loc[
            (
                dataframe['trend_bullish'] &  # 趋势向上
                (dataframe['conditions_met'] >= self.min_conditions.value) &  # 满足足够条件
                dataframe['price_near_high'] &  # 价格接近近期高点
                (dataframe['atr_pct'] > 0.35) &  # 波动率过滤
                (dataframe['volume'] > 0) &
                (dataframe['close'] > 0)
            ),
            'enter_long'] = 1
        
        dataframe.loc[dataframe['enter_long'] == 1, 'enter_tag'] = 'trend_param_opt2'
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI过高或价格跌破重要均线时退出
        dataframe.loc[
            (
                (dataframe['rsi'] > 75) |  # RSI过高
                (dataframe['close'] < dataframe['ma_slow'] * 0.975)  # 跌破慢线2.5%
            ),
            'exit_long'] = 1
        
        return dataframe
    
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                           proposed_stake: float, min_stake: Optional[float], max_stake: float,
                           leverage: float, entry_tag: Optional[str], side: str,
                           **kwargs) -> float:
        wallet = self.wallets.get_total_stake_amount()
        max_stake_amount = wallet * self.max_position_pct.value
        return min(proposed_stake, max_stake_amount)
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        return 1.0