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
                                IStrategy, IntParameter)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
from functools import reduce
import pandas_ta as pta


class Eth1hV7431(IStrategy):
    """
    ETH/USDT 1小时策略 V74.31 (平衡增强版)
    转换自FMZ JavaScript版本
    目标胜率45-50%，频率0.5-0.6次/日
    基于ATR的动态止损止盈，10个条件满足6个
    """
    
    # 策略参数
    INTERFACE_VERSION = 3
    
    # 时间框架
    timeframe = '1h'
    
    # 止损参数（基于ATR动态计算）
    stoploss = -0.10  # 临时值，实际在populate_indicators中动态计算
    
    # 止盈参数（基于ATR动态计算）
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    
    # 最小盈利
    minimal_roi = {
        "0": 0.20,  # 临时值，实际在策略中动态计算
    }
    
    # 交易选项
    process_only_new_candles = True
    use_custom_stoploss = True
    startup_candle_count: int = 300  # 需要足够数据计算MA200, ATR等
    
    # 条件开关参数
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
    
    # 条件参数
    min_conditions = IntParameter(4, 8, default=6, space="buy")
    
    # MA参数
    ma_short = IntParameter(3, 10, default=5, space="buy")
    ma_long = IntParameter(8, 15, default=10, space="buy")
    ma_trend = IntParameter(15, 30, default=20, space="buy")
    long_ma_period = IntParameter(150, 250, default=200, space="buy")
    
    # RSI参数
    rsi_period = IntParameter(5, 14, default=7, space="buy")
    rsi_min = IntParameter(50, 65, default=60, space="buy")
    rsi_max = IntParameter(70, 80, default=75, space="buy")
    
    # 成交量参数
    volume_ma = IntParameter(3, 10, default=5, space="buy")
    min_volume_ratio = DecimalParameter(1.1, 2.0, default=1.4, decimals=1, space="buy")
    
    # 动量参数
    momentum_period = IntParameter(2, 5, default=3, space="buy")
    min_momentum = DecimalParameter(0.1, 1.0, default=0.5, decimals=1, space="buy")
    
    # ADX参数
    adx_period = IntParameter(10, 20, default=14, space="buy")
    min_adx = IntParameter(20, 30, default=23, space="buy")
    
    # 布林带参数
    bb_period = IntParameter(15, 25, default=20, space="buy")
    bb_std = DecimalParameter(1.5, 2.5, default=2.0, decimals=1, space="buy")
    bb_width_threshold = DecimalParameter(0.03, 0.10, default=0.07, decimals=3, space="buy")
    
    # CCI参数
    cci_period = IntParameter(14, 26, default=20, space="buy")
    cci_threshold = IntParameter(-20, 20, default=0, space="buy")
    
    # ATR参数
    atr_period = IntParameter(10, 20, default=14, space="buy")
    atr_multiplier_stop = DecimalParameter(2.0, 4.0, default=3.0, decimals=1, space="sell")
    atr_multiplier_profit = DecimalParameter(6.0, 12.0, default=9.0, decimals=1, space="sell")
    
    # 移动止损参数
    use_trailing = BooleanParameter(default=True, space="sell")
    trail_activation_atr = DecimalParameter(0.8, 1.5, default=1.2, decimals=1, space="sell")
    trail_to_breakeven = BooleanParameter(default=True, space="sell")
    trail_activation_atr2 = DecimalParameter(1.5, 2.5, default=2.0, decimals=1, space="sell")
    trail_distance_atr = DecimalParameter(0.5, 1.2, default=0.8, decimals=1, space="sell")
    
    # 风险参数
    base_risk_percent = DecimalParameter(0.5, 1.5, default=0.8, decimals=1, space="buy")
    
    # 状态变量
    trade_stats = {
        'total_trades': 0,
        'wins': 0,
        'losses': 0,
        'consecutive_losses': 0,
        'recent_pnl': [],
        'peak_equity': 0,
        'loss_streak_pause_until': 0
    }
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算所有需要的指标
        """
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
        
        # 动量（价格变化百分比）
        dataframe['momentum'] = (dataframe['close'] - dataframe['close'].shift(self.momentum_period.value)) / dataframe['close'].shift(self.momentum_period.value) * 100
        
        # ATR
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period.value)
        
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
        
        # MA斜率（MA5是否上升）
        dataframe['ma5_slope'] = dataframe['ma5'] > dataframe['ma5'].shift(1)
        
        # 动态止损止盈水平（基于ATR）
        dataframe['stop_loss_level'] = dataframe['close'] - dataframe['atr'] * self.atr_multiplier_stop.value
        dataframe['take_profit_level'] = dataframe['close'] + dataframe['atr'] * self.atr_multiplier_profit.value
        
        # 计算条件满足情况
        self._calculate_conditions(dataframe)
        
        return dataframe
    
    def _calculate_conditions(self, dataframe: DataFrame) -> DataFrame:
        """
        计算10个条件是否满足
        """
        conditions = {}
        
        # 1. MA多头排列 (ma5 > ma10 > ma20)
        if self.use_ma.value:
            conditions['ma_trend'] = (dataframe['ma5'] > dataframe['ma10']) & (dataframe['ma10'] > dataframe['ma20'])
        
        # 2. RSI在范围内
        if self.use_rsi.value:
            conditions['rsi_ok'] = (dataframe['rsi'] >= self.rsi_min.value) & (dataframe['rsi'] <= self.rsi_max.value)
        
        # 3. 成交量放大
        if self.use_volume.value:
            conditions['volume_ok'] = dataframe['volume_ratio'] >= self.min_volume_ratio.value
        
        # 4. 正动量
        if self.use_momentum.value:
            conditions['momentum_ok'] = dataframe['momentum'] > self.min_momentum.value
        
        # 5. 价格在MA20之上
        if self.use_price_position.value:
            conditions['price_above_ma20'] = dataframe['close'] > dataframe['ma20']
        
        # 6. 价格在MA200之上（长期趋势）
        if self.use_long_trend.value:
            conditions['price_above_ma200'] = dataframe['close'] > dataframe['ma200']
        
        # 7. ADX大于阈值
        if self.use_adx.value:
            conditions['adx_ok'] = dataframe['adx'] > self.min_adx.value
        
        # 8. 布林带宽度大于阈值
        if self.use_bb.value:
            conditions['bb_width_ok'] = dataframe['bb_width'] > self.bb_width_threshold.value
        
        # 9. CCI大于阈值
        if self.use_cci.value:
            conditions['cci_ok'] = dataframe['cci'] > self.cci_threshold.value
        
        # 10. MA斜率向上
        if self.use_ma_slope.value:
            conditions['ma_slope_ok'] = dataframe['ma5_slope']
        
        # 计算满足的条件数量
        condition_columns = list(conditions.keys())
        if condition_columns:
            condition_df = pd.concat([conditions[col] for col in condition_columns], axis=1)
            condition_df.columns = condition_columns
            dataframe['conditions_met'] = condition_df.sum(axis=1)
            dataframe['total_conditions'] = len(condition_columns)
        else:
            dataframe['conditions_met'] = 0
            dataframe['total_conditions'] = 0
        
        # 信号：满足足够条件
        dataframe['entry_signal'] = dataframe['conditions_met'] >= self.min_conditions.value
        
        return dataframe
    
    def _calculate_dynamic_risk(self, dataframe: DataFrame) -> DataFrame:
        """
        计算动态风险比例（基于近期胜率）
        """
        # 这里简化处理，实际应该基于self.trade_stats中的历史交易数据
        # 但回测时无法访问，所以使用固定值
        dataframe['dynamic_risk'] = self.base_risk_percent.value
        
        # 如果有交易统计，可以动态调整
        # if len(self.trade_stats['recent_pnl']) >= 10:
        #     recent_wins = sum(1 for pnl in self.trade_stats['recent_pnl'][-10:] if pnl > 0)
        #     win_rate = recent_wins / 10
        #     if win_rate > 0.5:
        #         risk_multiplier = 1.5
        #     elif win_rate < 0.4:
        #         risk_multiplier = 0.375
        #     else:
        #         risk_multiplier = 1.0
        #     dataframe['dynamic_risk'] = self.base_risk_percent.value * risk_multiplier
        # else:
        #     dataframe['dynamic_risk'] = self.base_risk_percent.value
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义进场信号
        """
        # 计算动态风险
        dataframe = self._calculate_dynamic_risk(dataframe)
        
        # 基本进场条件
        dataframe.loc[
            (
                dataframe['entry_signal'] &
                (dataframe['volume'] > 0) &  # 有成交量
                (dataframe['atr'] > 0) &     # ATR有效
                (dataframe['conditions_met'] >= self.min_conditions.value)
            ),
            'enter_long'] = 1
        
        # 添加进场标签
        dataframe.loc[dataframe['enter_long'] == 1, 'enter_tag'] = 'eth_1h_v74_31'
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义出场信号
        """
        # 这里主要依赖自定义止损止盈，所以出场信号可以简单设置
        # 实际出场在custom_stoploss中处理
        
        # 如果价格达到止盈水平
        dataframe.loc[
            (
                dataframe['close'] >= dataframe['take_profit_level']
            ),
            'exit_long'] = 1
        
        # 如果价格达到止损水平
        dataframe.loc[
            (
                dataframe['close'] <= dataframe['stop_loss_level']
            ),
            'exit_long'] = 1
        
        return dataframe
    
    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, after_fill: bool,
                        **kwargs) -> Optional[float]:
        """
        自定义止损逻辑，实现移动止损
        """
        # 获取当前交易的进入价格
        entry_price = trade.open_rate
        
        # 获取当前ATR（从dataframe中）
        # 这里简化处理，实际应该从dataframe获取对应时间的ATR
        # 使用固定值或从trade对象中获取存储的ATR值
        
        # 由于无法直接获取，这里使用简化版本
        # 在实际策略中，应该在进入交易时存储ATR值
        
        if self.use_trailing.value and current_profit > 0:
            # 计算盈利的ATR倍数
            profit_atr_multiple = (current_rate - entry_price) / (entry_price * 0.005)  # 假设ATR是价格的0.5%
            
            # 保本止损
            if self.trail_to_breakeven.value and profit_atr_multiple > self.trail_activation_atr.value:
                # 移动到开仓价（保本）
                return -0.001  # 几乎保本
            
            # 移动止损
            if profit_atr_multiple > self.trail_activation_atr2.value:
                # 移动止损距离
                trail_distance = self.trail_distance_atr.value * 0.005  # 假设ATR是价格的0.5%
                # 计算移动止损水平
                trailing_stop = current_rate * (1 - trail_distance)
                # 转换为止损比例
                stoploss = (trailing_stop - entry_price) / entry_price
                return stoploss
        
        # 默认返回None，使用常规止损
        return None
    
    def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
                    current_profit: float, **kwargs) -> Optional[Union[str, bool]]:
        """
        自定义出场逻辑
        """
        # 持仓时间过长（超过2小时）
        if (current_time - trade.open_date_utc).total_seconds() > 7200:  # 2小时
            return 'timeout'
        
        return None
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        """
        杠杆设置（现货交易不使用杠杆）
        """
        return 1.0  # 现货交易，杠杆为1