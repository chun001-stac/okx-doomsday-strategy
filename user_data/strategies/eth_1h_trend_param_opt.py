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


class Eth1hTrendParamOpt(IStrategy):
    """
    ETH 1小时策略 - 趋势过滤 + 参数优化版
    基于V74.31，添加趋势过滤，放宽参数，降低条件门槛
    只在上涨趋势中交易（价格>200MA且200MA向上）
    """
    
    INTERFACE_VERSION = 3
    timeframe = '1h'
    
    # 止损止盈 - 基于ATR动态计算，但使用固定值简化
    stoploss = -0.018  # 1.8% 止损（原策略基于ATR，这里简化）
    minimal_roi = {
        "0": 0.054,    # 5.4% 止盈（盈亏比3:1）
        "30": 0.027,   # 30分钟后如果盈利2.7%则退出
        "60": 0.0135,  # 60分钟后如果盈利1.35%则退出
        "120": 0       # 120分钟后保本退出
    }
    
    process_only_new_candles = True
    use_custom_stoploss = False  # 简化，使用固定止损
    startup_candle_count: int = 250  # 需要计算200MA
    
    # === 趋势参数 ===
    trend_ma_period = IntParameter(180, 220, default=200, space="buy")
    
    # === 条件参数（放宽版） ===
    # MA参数
    ma_short = IntParameter(4, 8, default=6, space="buy")
    ma_long = IntParameter(8, 15, default=12, space="buy")
    ma_trend = IntParameter(15, 25, default=18, space="buy")
    
    # RSI参数（放宽）
    rsi_period = IntParameter(6, 12, default=8, space="buy")
    rsi_min = IntParameter(48, 58, default=53, space="buy")  # 从60降低
    rsi_max = IntParameter(65, 75, default=70, space="buy")  # 从75降低
    
    # 成交量参数（放宽）
    volume_ma_period = IntParameter(4, 8, default=6, space="buy")
    volume_ratio_min = DecimalParameter(1.1, 1.5, default=1.25, decimals=2, space="buy")  # 从1.4降低
    
    # 动量参数
    momentum_period = IntParameter(2, 4, default=3, space="buy")
    momentum_min = DecimalParameter(0.2, 0.6, default=0.35, decimals=2, space="buy")  # 从0.5降低
    
    # ADX参数（放宽）
    adx_period = IntParameter(12, 18, default=14, space="buy")
    adx_min = IntParameter(18, 25, default=21, space="buy")  # 从23降低
    
    # 布林带参数
    bb_period = IntParameter(18, 22, default=20, space="buy")
    bb_std = DecimalParameter(1.8, 2.2, default=2.0, decimals=1, space="buy")
    bb_width_min = DecimalParameter(0.04, 0.08, default=0.06, decimals=3, space="buy")  # 从0.07降低
    
    # CCI参数
    cci_period = IntParameter(18, 22, default=20, space="buy")
    cci_threshold = IntParameter(-5, 5, default=0, space="buy")
    
    # === 条件门槛 ===
    min_conditions = IntParameter(4, 6, default=5, space="buy")  # 从6降低到5
    
    # === 风险管理 ===
    max_position_pct = DecimalParameter(0.05, 0.10, default=0.07, decimals=2, space="buy")
    trade_cooldown = IntParameter(3, 6, default=4, space="buy")  # 小时
    
    # === 状态变量 ===
    last_trade_time = None
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 趋势均线
        dataframe['ma_trend'] = dataframe['close'].rolling(window=self.trend_ma_period.value).mean()
        # 判断200MA是否向上（当前值 > 20小时前值）
        dataframe['ma_trend_up'] = dataframe['ma_trend'] > dataframe['ma_trend'].shift(20)
        dataframe['trend_bullish'] = (dataframe['close'] > dataframe['ma_trend']) & dataframe['ma_trend_up']
        
        # 快慢均线（用于MA多头排列）
        dataframe['ma_fast'] = dataframe['close'].rolling(window=self.ma_short.value).mean()
        dataframe['ma_mid'] = dataframe['close'].rolling(window=self.ma_long.value).mean()
        dataframe['ma_slow'] = dataframe['close'].rolling(window=self.ma_trend.value).mean()
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
        
        # MA斜率（MA快线是否上升）
        dataframe['ma_slope'] = dataframe['ma_fast'] > dataframe['ma_fast'].shift(1)
        
        # 价格位置
        dataframe['price_above_ma_slow'] = dataframe['close'] > dataframe['ma_slow']
        dataframe['price_above_ma_trend'] = dataframe['close'] > dataframe['ma_trend']
        
        # ATR（用于过滤低波动）
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
        
        # 6. 价格在趋势线之上（与趋势过滤不同，这是单独条件）
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
            # 将条件列表转换为DataFrame
            cond_df = pd.concat(conditions, axis=1)
            cond_df.columns = [f'cond_{i}' for i in range(len(conditions))]
            dataframe['conditions_met'] = cond_df.sum(axis=1)
            dataframe['total_conditions'] = len(conditions)
        else:
            dataframe['conditions_met'] = 0
            dataframe['total_conditions'] = 0
        
        # 信号强度
        dataframe['signal_strength'] = dataframe['conditions_met'] / dataframe['total_conditions']
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 核心进场条件：趋势向上 + 满足足够条件 + 波动率足够
        dataframe.loc[
            (
                dataframe['trend_bullish'] &  # 趋势向上
                (dataframe['conditions_met'] >= self.min_conditions.value) &  # 满足足够条件
                (dataframe['atr_pct'] > 0.4) &  # 过滤低波动
                (dataframe['volume'] > 0) &
                (dataframe['close'] > 0)
            ),
            'enter_long'] = 1
        
        dataframe.loc[dataframe['enter_long'] == 1, 'enter_tag'] = 'trend_param_opt'
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI过高或价格跌破重要均线时退出
        dataframe.loc[
            (
                (dataframe['rsi'] > 78) |  # RSI过高
                (dataframe['close'] < dataframe['ma_slow'] * 0.98)  # 跌破慢线2%
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
        return 1.0  # 现货
    
    # 可选：添加交易冷却逻辑
    def adjust_trade_position(self, trade, current_time: datetime, current_rate: float,
                              current_profit: float, min_stake: float, max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs):
        # 这里可以添加交易冷却逻辑，但Freqtrade的adjust_trade_position主要用于调整仓位
        # 交易冷却可以通过其他方式实现，例如在populate_entry_trend中添加时间过滤
        return None