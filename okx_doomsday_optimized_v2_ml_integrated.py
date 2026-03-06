#!/usr/bin/env python3
"""
OKX末日战车策略 - 修复版（修复51010错误）
基于原优化版修改，修复OKX模拟账户下单问题
"""

import os
import sys
import time
import json
import logging
import configparser
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
import pandas as pd
import numpy as np
import ccxt
import talib
from dataclasses import dataclass, field
import hashlib
import requests
import warnings
import ml_data_collector
warnings.filterwarnings('ignore')


# ==================== 配置类（添加修复参数） ====================
@dataclass
class Config:
    """交易配置 - 优化版v2（支持6个优化点）"""
    # OKX API配置
    api_key: str = ""
    api_secret: str = ""
    api_password: str = ""  # OKX需要passphrase
    
    # 交易对 (OKX格式: ETH-USDT-SWAP)
    symbol: str = "ETH-USDT-SWAP"
    base_currency: str = "ETH"
    quote_currency: str = "USDT"
    
    # 杠杆设置
    leverage: int = 10  # 10倍杠杆
    margin_mode: str = "cross"  # 改为全仓模式，模拟账户通常是net_mode
    
    # 交易模式（修复51010错误）
    td_mode: str = "cross"  # 交易模式: cross, isolated, cash
    
    # 动态仓位管理
    base_position_size_pct: float = 0.10  # 降低到10%
    max_position_size_pct: float = 0.20   # 最大仓位20%
    min_position_size_pct: float = 0.03   # 最小仓位3%
    atr_position_adjust: bool = True      # 根据ATR调整仓位
    
    # 交易限制
    max_daily_trades: int = 15           # 每日最大交易次数增加到15
    max_daily_loss_pct: float = 0.25     # 每日最大亏损25%
    max_total_loss_pct: float = 0.40     # 总最大亏损40%
    cooling_period_minutes: int = 5      # 连续亏损后冷却时间
    
    # 策略参数（优化）
    timeframe: str = "5m"                # 5分钟K线
    momentum_period: int = 5
    momentum_threshold_long: float = 0.005   # 做多动量阈值降低到0.5%
    momentum_threshold_short: float = -0.005  # 做空动量阈值降低到-0.5%
    rsi_period: int = 7
    rsi_overbought: int = 75             # 放宽超买线
    rsi_oversold: int = 25               # 放宽超卖线
    short_bias: float = 0.75             # 75%做空侧重
    
    # 动态止损止盈（优化）
    base_stoploss_pct: float = 0.20      # 基础止损20%
    base_takeprofit_pct: float = 0.25    # 基础止盈25%
    atr_stoploss_multiplier: float = 2.0  # ATR止损倍数降低到2.0
    atr_takeprofit_multiplier: float = 2.5  # ATR止盈倍数降低到2.5
    trailing_stop_pct: float = 0.06      # 移动止损6%
    trailing_takeprofit_trigger_pct: float = 0.05  # 移动止盈触发阈值5%
    trailing_takeprofit_pct: float = 0.02  # 移动止盈回撤2%
    
    # 信号过滤（优化）
    min_volume_ratio: float = 1.2        # 最小成交量比率降低到1.2
    max_atr_pct: float = 0.05            # 最大ATR百分比增加到5%
    trend_confirmation_period: int = 3   # 趋势确认周期
    
    # ========== 新增：6个优化点参数 ==========
    # 1. 信号强度阈值
    signal_strength_threshold: float = 20.0  # 信号强度阈值（原15）
    
    # 2. 信号强度权重（优化计算）
    # 权重将在load_config中通过JSON解析，这里先定义默认值
    signal_strength_weights_json: str = '{"momentum": 0.15, "volume": 0.10, "rsi": 0.15, "trend": 0.20, "bb": 0.10, "volatility": 0.10, "multi_timeframe": 0.10, "sentiment": 0.10}'
    
    # 3. 动态仓位分配
    position_size_by_strength: bool = True  # 是否根据信号强度调整仓位
    strength_to_position_power: float = 1.5  # 信号强度对仓位的影响强度（指数）
    
    # 4. 多时间框架确认
    multi_timeframe_confirmation: bool = True  # 是否启用多时间框架确认
    higher_timeframe: str = "1h"  # 更高时间框架
    higher_timeframe_weight: float = 0.3  # 更高时间框架权重（0-1）
    
    # 5. 止损止盈优化
    stop_loss_volatility_adjust: bool = True  # 根据波动率调整止损
    stop_loss_trend_adjust: bool = True  # 根据趋势调整止损
    volatility_stop_multiplier: float = 2.0  # 波动率止损乘数（高波动时增加止损）
    trend_stop_multiplier: float = 1.5  # 趋势止损乘数（顺趋势时放宽止损）
    
    # 6. 机器学习信号评分（暂不实现，预留）
    ml_signal_scoring: bool = False  # 是否启用机器学习信号评分
    ml_model_path: str = ""  # 模型路径
    
    # 系统设置
    check_interval: int = 60             # 检查间隔(秒)
    enable_trading: bool = True          # 启用交易
    testnet: bool = True                 # 使用测试网
    enable_logging: bool = True          # 启用详细日志
    cache_indicators: bool = True        # 缓存技术指标
    use_simple_orders: bool = True       # 使用简单订单，后设置止损止盈


# ==================== 信号生成器（保持原优化版） ====================
class OptimizedSignalGenerator:
    """优化信号生成器 - 减少假信号，提高胜率"""
    
    def __init__(self, config: Config, exchange: ccxt.Exchange = None):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.cache = {}  # 指标缓存
        self.current_short_bias = config.short_bias  # 动态做空侧重，受舆情影响
        self.current_sentiment_score = 0.0  # 当前舆情分数（-1到+1）
        self.exchange = exchange  # 用于获取多时间框架数据
        
        # 解析信号强度权重
        try:
            self.signal_strength_weights = json.loads(config.signal_strength_weights_json)
            self.logger.info(f"信号强度权重: {self.signal_strength_weights}")
        except Exception as e:
            self.logger.error(f"解析信号强度权重失败: {e}，使用默认权重")
            self.signal_strength_weights = {
                "momentum": 0.15, "volume": 0.10, "rsi": 0.15, "trend": 0.20,
                "bb": 0.10, "volatility": 0.10, "multi_timeframe": 0.10, "sentiment": 0.10
            }
        
        # 多时间框架数据缓存
        self.higher_timeframe_data = None
        self.higher_timeframe_last_update = 0
        
    def _get_cache_key(self, df: pd.DataFrame, indicator_name: str) -> str:
        """生成缓存键"""
        data_hash = hashlib.md5(pd.util.hash_pandas_object(df.tail(50)).values).hexdigest()
        return f"{indicator_name}_{data_hash}"
    
    def update_sentiment_bias(self, sentiment_score: float):
        """
        根据舆情分数更新做空侧重（非线性映射）
        sentiment_score: -1 (极端看空) 到 +1 (极端看多)
        """
        # 非线性映射：极端情绪放大影响，温和情绪弱化影响
        abs_sentiment = abs(sentiment_score)
        
        if abs_sentiment > 0.5:  # 强烈情绪（分数绝对值>0.5）
            # 使用较大系数：每±1.0舆情调整±0.3
            adjustment = sentiment_score * 0.3
        else:  # 温和情绪（分数绝对值≤0.5）
            # 使用较小系数：每±1.0舆情调整±0.15
            adjustment = sentiment_score * 0.15
        
        # 计算新的做空侧重
        new_bias = self.config.short_bias - adjustment  # 减号：舆情分数正（看多）→ 做空侧重降低
        # 限制范围在0.2到0.8之间
        self.current_short_bias = max(0.2, min(0.8, new_bias))
        # 保存舆情分数
        self.current_sentiment_score = sentiment_score
        
        # 记录日志
        emotion_level = "强烈看多" if sentiment_score > 0.5 else \
                       "温和看多" if sentiment_score > 0 else \
                       "温和看空" if sentiment_score > -0.5 else \
                       "强烈看空"
        self.logger.info(f"舆情分数: {sentiment_score:.2f} ({emotion_level}), 动态做空侧重: {self.current_short_bias:.2f}")
    
    def fetch_higher_timeframe_data(self, limit: int = 100) -> Optional[pd.DataFrame]:
        """获取更高时间框架数据"""
        if not self.config.multi_timeframe_confirmation or self.exchange is None:
            return None
        
        # 每10分钟更新一次
        current_time = time.time()
        if (self.higher_timeframe_data is not None and 
            current_time - self.higher_timeframe_last_update < 600):
            return self.higher_timeframe_data
        
        try:
            ohlcv = self.exchange.fetch_ohlcv(
                self.config.symbol,
                timeframe=self.config.higher_timeframe,
                limit=limit
            )
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # 计算简单趋势指标
            df['ma_fast'] = df['close'].rolling(window=5).mean()
            df['ma_slow'] = df['close'].rolling(window=20).mean()
            df['trend'] = df.apply(
                lambda row: 1 if row['ma_fast'] > row['ma_slow'] else -1 if row['ma_fast'] < row['ma_slow'] else 0,
                axis=1
            )
            
            self.higher_timeframe_data = df
            self.higher_timeframe_last_update = current_time
            
            self.logger.info(f"更高时间框架({self.config.higher_timeframe})数据获取成功，最新趋势: {df['trend'].iloc[-1]}")
            return df
            
        except Exception as e:
            self.logger.error(f"获取更高时间框架数据失败: {e}")
            return None
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算交易信号（优化版）"""
        if len(df) < 100:
            self.logger.warning(f"数据不足，只有{len(df)}根K线，需要至少100根")
            df['signal'] = 'hold'
            df['signal_strength'] = 0.0
            df['position_size'] = 0.0
            return df
        
        try:
            # ========== 技术指标计算（带缓存） ==========
            cache_key = self._get_cache_key(df, 'indicators')
            if self.config.cache_indicators and cache_key in self.cache:
                cached_result = self.cache[cache_key]
                df = df.copy()
                # 将缓存的指标列复制到df中（包括可能缺失的列）
                ohlcv_columns = ['open', 'high', 'low', 'close', 'volume']
                for col in cached_result.columns:
                    if col not in ohlcv_columns:
                        df[col] = cached_result[col]
            else:
                df = self._calculate_indicators(df)
                if self.config.cache_indicators:
                    self.cache[cache_key] = df[list(set(df.columns) - set(['open', 'high', 'low', 'close', 'volume']))].copy()
            
            # ========== 多时间框架数据获取 ==========
            higher_timeframe_data = None
            if self.config.multi_timeframe_confirmation:
                higher_timeframe_data = self.fetch_higher_timeframe_data()
                if higher_timeframe_data is not None:
                    self.logger.info(f"多时间框架确认已启用，{self.config.higher_timeframe}趋势: {higher_timeframe_data['trend'].iloc[-1] if 'trend' in higher_timeframe_data.columns else '未知'}")
                else:
                    self.logger.warning("获取多时间框架数据失败，将继续使用单时间框架信号")
            else:
                self.logger.debug("多时间框架确认未启用")
            
            # ========== 信号生成（优化逻辑） ==========
            df = self._generate_signals(df, higher_timeframe_data)
            
            # ========== 信号过滤（新增） ==========
            df = self._filter_signals(df)
            
            # ========== 仓位大小计算 ==========
            df = self._calculate_position_size(df)
            
            # 信号统计
            long_count = (df['signal'] == 'long').sum()
            short_count = (df['signal'] == 'short').sum()
            self.logger.info(f"信号统计: 做多={long_count}, 做空={short_count}, 有效信号率={((long_count+short_count)/len(df)*100):.1f}%")
            
        except Exception as e:
            self.logger.error(f"计算信号时出错: {e}", exc_info=True)
            df['signal'] = 'hold'
            df['signal_strength'] = 0.0
            df['position_size'] = 0.0
        
        return df
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标（优化版）"""
        # 动量指标
        df['momentum'] = df['close'].pct_change(periods=self.config.momentum_period)
        df['momentum_3'] = df['close'].pct_change(periods=3)
        df['momentum_7'] = df['close'].pct_change(periods=7)
        df['momentum_acc'] = df['momentum'].diff()
        
        # 成交量分析
        df['volume_ma'] = df['volume'].rolling(window=10).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        df['volume_spike'] = df['volume_ratio'] > 2.5
        df['volume_trend'] = df['volume'].rolling(window=20).apply(
            lambda x: 1 if x.iloc[-1] > x.mean() else -1 if x.iloc[-1] < x.mean() else 0
        )
        
        # RSI系列
        df['rsi'] = talib.RSI(df['close'], timeperiod=self.config.rsi_period)
        df['rsi_slow'] = talib.RSI(df['close'], timeperiod=14)
        df['rsi_trend'] = df['rsi'].rolling(window=5).mean() - df['rsi'].rolling(window=20).mean()
        
        # 布林带（多参数）
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
            df['close'], timeperiod=15, nbdevup=2.0, nbdevdn=2.0
        )
        df['bb_upper2'], df['bb_middle2'], df['bb_lower2'] = talib.BBANDS(
            df['close'], timeperiod=20, nbdevup=1.5, nbdevdn=1.5
        )
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        df['bb_position'] = df['bb_position'].clip(0, 1)
        
        # 突破信号（多时间框架）
        df['high_15'] = df['high'].rolling(window=15).max()
        df['low_15'] = df['low'].rolling(window=15).min()
        df['high_30'] = df['high'].rolling(window=30).max()
        df['low_30'] = df['low'].rolling(window=30).min()
        
        # 波动率分析
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        df['atr_pct'] = df['atr'] / df['close']
        df['atr_ma'] = df['atr_pct'].rolling(window=20).mean()
        df['volatility_regime'] = df['atr_pct'].rolling(window=10).apply(
            lambda x: 2 if x.iloc[-1] > x.mean() * 1.5 else 0 if x.iloc[-1] < x.mean() * 0.5 else 1
        )
        
        # 趋势强度
        df['ma_fast'] = df['close'].rolling(window=5).mean()
        df['ma_medium'] = df['close'].rolling(window=15).mean()
        df['ma_slow'] = df['close'].rolling(window=30).mean()
        
        df['trend_strength'] = df.apply(
            lambda row: 2 if (row['ma_fast'] > row['ma_medium'] > row['ma_slow']) else
            -2 if (row['ma_fast'] < row['ma_medium'] < row['ma_slow']) else 0,
            axis=1
        )
        
        return df
    
    def _generate_signals(self, df: pd.DataFrame, higher_timeframe_data: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """生成交易信号（三重验证）"""
        df['signal'] = 'hold'
        df['signal_strength'] = 0.0
        
        # 条件1：动量突破（做多条件）
        long_condition1 = (
            (df['momentum'] > self.config.momentum_threshold_long) &
            (df['momentum_acc'] > 0) &
            (df['volume_ratio'] > self.config.min_volume_ratio) &
            (df['rsi'] > self.config.rsi_oversold) & (df['rsi'] < self.config.rsi_overbought) &
            (df['atr_pct'] < self.config.max_atr_pct)
        )
        
        # 条件2：超卖反弹（做多条件）
        long_condition2 = (
            (df['rsi'] < self.config.rsi_oversold) &
            (df['momentum_3'] > 0) &
            (df['bb_position'] < 0.2) &
            (df['volume_spike']) &
            (df['trend_strength'] >= 0)
        )
        
        # 条件3：趋势跟随（做多条件）
        long_condition3 = (
            (df['trend_strength'] > 0) &
            (df['momentum_7'] > 0.01) &
            (df['close'] > df['ma_fast']) &
            (df['volume_trend'] > 0) &
            (df['volatility_regime'] < 2)
        )
        
        # 条件4：弱势突破（做空条件）
        short_condition1 = (
            (df['momentum'] < self.config.momentum_threshold_short) &
            (df['momentum_acc'] < 0) &
            (df['volume_ratio'] > self.config.min_volume_ratio) &
            (df['rsi'] > self.config.rsi_oversold) & (df['rsi'] < self.config.rsi_overbought) &
            (df['atr_pct'] < self.config.max_atr_pct)
        )
        
        # 条件5：超买回调（做空条件）
        short_condition2 = (
            (df['rsi'] > self.config.rsi_overbought) &
            (df['momentum_3'] < 0) &
            (df['bb_position'] > 0.8) &
            (df['volume_spike']) &
            (df['trend_strength'] <= 0)
        )
        
        # 条件6：趋势跟随（做空条件）
        short_condition3 = (
            (df['trend_strength'] < 0) &
            (df['momentum_7'] < -0.01) &
            (df['close'] < df['ma_fast']) &
            (df['volume_trend'] < 0) &
            (df['volatility_regime'] < 2)
        )
        
        # 分配信号（做空侧重）
        random_bias = np.random.random(len(df))
        
        # 做多信号（需要随机偏置 > short_bias）
        long_mask = ((long_condition1 | long_condition2 | long_condition3) & 
                    (random_bias > self.current_short_bias))
        df.loc[long_mask, 'signal'] = 'long'
        
        # 做空信号（需要随机偏置 <= short_bias）
        short_mask = ((short_condition1 | short_condition2 | short_condition3) & 
                     (random_bias <= self.current_short_bias))
        df.loc[short_mask, 'signal'] = 'short'
        
        # 计算信号强度（传递更高时间框架数据）
        df = self._calculate_signal_strength(df, higher_timeframe_data)
        
        return df
    
    def _calculate_signal_strength(self, df: pd.DataFrame, higher_timeframe_data: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """计算信号强度（0-100分） - 优化版，支持多时间框架和舆情"""
        df['signal_strength'] = 0.0
        
        # ========== 1. 动量分数（0-100分归一化） ==========
        df.loc[df['signal'] == 'long', 'momentum_score'] = np.clip(
            df['momentum'] / 0.015 * 100, 0, 100
        )
        df.loc[df['signal'] == 'short', 'momentum_score'] = np.clip(
            abs(df['momentum']) / 0.015 * 100, 0, 100
        )
        
        # ========== 2. 成交量分数（0-100分） ==========
        df['volume_score'] = np.clip(
            (df['volume_ratio'] - 1) * 50, 0, 100  # volume_ratio=1 → 0分, volume_ratio=3 → 100分
        )
        
        # ========== 3. RSI分数（0-100分） ==========
        df.loc[df['signal'] == 'long', 'rsi_score'] = np.clip(
            (70 - df['rsi']) / 40 * 100, 0, 100
        )
        df.loc[df['signal'] == 'short', 'rsi_score'] = np.clip(
            (df['rsi'] - 30) / 40 * 100, 0, 100
        )
        
        # ========== 4. 趋势分数（0-100分） ==========
        df.loc[df['signal'] == 'long', 'trend_score'] = np.clip(
            (df['trend_strength'] + 2) / 4 * 100, 0, 100  # trend_strength范围-2到2
        )
        df.loc[df['signal'] == 'short', 'trend_score'] = np.clip(
            (abs(df['trend_strength']) + 2) / 4 * 100, 0, 100
        )
        
        # ========== 5. 布林带分数（0-100分） ==========
        df.loc[df['signal'] == 'long', 'bb_score'] = np.clip(
            (1 - df['bb_position']) * 100, 0, 100
        )
        df.loc[df['signal'] == 'short', 'bb_score'] = np.clip(
            df['bb_position'] * 100, 0, 100
        )
        
        # ========== 6. 波动率分数（0-100分） ==========
        df['volatility_score'] = np.clip(
            (0.03 - df['atr_pct']) / 0.03 * 100, 0, 100
        )
        
        # ========== 7. 多时间框架分数（0-100分） ==========
        df['multi_timeframe_score'] = 50  # 默认中性
        if higher_timeframe_data is not None and len(higher_timeframe_data) > 0:
            # 获取最新更高时间框架趋势
            latest_trend = higher_timeframe_data['trend'].iloc[-1] if 'trend' in higher_timeframe_data.columns else 0
            for idx, row in df.iterrows():
                if row['signal'] == 'long':
                    # 做多信号：更高时间框架趋势向上则加分，向下则减分
                    if latest_trend > 0:
                        df.at[idx, 'multi_timeframe_score'] = 80
                    elif latest_trend < 0:
                        df.at[idx, 'multi_timeframe_score'] = 20
                    else:
                        df.at[idx, 'multi_timeframe_score'] = 50
                elif row['signal'] == 'short':
                    # 做空信号：更高时间框架趋势向下则加分，向上则减分
                    if latest_trend < 0:
                        df.at[idx, 'multi_timeframe_score'] = 80
                    elif latest_trend > 0:
                        df.at[idx, 'multi_timeframe_score'] = 20
                    else:
                        df.at[idx, 'multi_timeframe_score'] = 50
        
        # ========== 8. 舆情分数（0-100分） ==========
        df['sentiment_score'] = 50.0  # 默认中性
        # 根据当前舆情分数和信号方向调整
        sentiment = self.current_sentiment_score  # -1到+1
        for idx, row in df.iterrows():
            if row['signal'] == 'long':
                # 做多信号：舆情分数正（看多）加分，负（看空）减分
                # sentiment从-1到+1映射到0-100分，但需要非线性：+1→80分，-1→20分，0→50分
                sentiment_score_value = 50 + sentiment * 30  # -1→20, 0→50, +1→80
                df.at[idx, 'sentiment_score'] = np.clip(sentiment_score_value, 0, 100)
            elif row['signal'] == 'short':
                # 做空信号：舆情分数负（看空）加分，正（看多）减分
                # 反向映射：-1→80分，+1→20分，0→50分
                sentiment_score_value = 50 - sentiment * 30  # -1→80, 0→50, +1→20
                df.at[idx, 'sentiment_score'] = np.clip(sentiment_score_value, 0, 100)
        # 记录舆情分数影响
        if any(df['signal'] != 'hold'):
            self.logger.debug(f"舆情分数影响: sentiment={sentiment:.2f}, 做多信号得分≈{50+sentiment*30:.0f}, 做空信号得分≈{50-sentiment*30:.0f}")
        
        # ========== 综合分数（加权平均） ==========
        for idx, row in df.iterrows():
            if row['signal'] in ['long', 'short']:
                scores = []
                weights = []
                
                # 动量分数
                if 'momentum_score' in row:
                    scores.append(row['momentum_score'])
                    weights.append(self.signal_strength_weights.get('momentum', 0.15))
                # 成交量分数
                if 'volume_score' in row:
                    scores.append(row['volume_score'])
                    weights.append(self.signal_strength_weights.get('volume', 0.10))
                # RSI分数
                if 'rsi_score' in row:
                    scores.append(row['rsi_score'])
                    weights.append(self.signal_strength_weights.get('rsi', 0.15))
                # 趋势分数
                if 'trend_score' in row:
                    scores.append(row['trend_score'])
                    weights.append(self.signal_strength_weights.get('trend', 0.20))
                # 布林带分数
                if 'bb_score' in row:
                    scores.append(row['bb_score'])
                    weights.append(self.signal_strength_weights.get('bb', 0.10))
                # 波动率分数
                if 'volatility_score' in row:
                    scores.append(row['volatility_score'])
                    weights.append(self.signal_strength_weights.get('volatility', 0.10))
                # 多时间框架分数
                if 'multi_timeframe_score' in row:
                    scores.append(row['multi_timeframe_score'])
                    weights.append(self.signal_strength_weights.get('multi_timeframe', 0.10))
                # 舆情分数
                if 'sentiment_score' in row:
                    scores.append(row['sentiment_score'])
                    weights.append(self.signal_strength_weights.get('sentiment', 0.10))
                
                # 归一化权重（确保总和为1）
                total_weight = sum(weights)
                if total_weight > 0:
                    weights = [w / total_weight for w in weights]
                    df.at[idx, 'signal_strength'] = np.average(scores, weights=weights)
                else:
                    df.at[idx, 'signal_strength'] = 0
        
        # 清理临时列
        temp_cols = ['momentum_score', 'volume_score', 'rsi_score', 'trend_score', 
                    'bb_score', 'volatility_score', 'multi_timeframe_score', 'sentiment_score']
        for col in temp_cols:
            if col in df.columns:
                df = df.drop(col, axis=1)
        
        return df
    
    def _filter_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """信号过滤（提高质量）"""
        # 记录原始信号数量
        original_signals = (df['signal'] != 'hold').sum()
        original_long = (df['signal'] == 'long').sum()
        original_short = (df['signal'] == 'short').sum()
        
        # 强度过滤（必须>阈值分，避免低质量信号）
        threshold = self.config.signal_strength_threshold
        strength_filtered = (df['signal'] != 'hold') & (df['signal_strength'] <= threshold)
        strength_filtered_count = strength_filtered.sum()
        df.loc[strength_filtered, 'signal'] = 'hold'
        
        # 波动率过滤（相对阈值优化：使用ATR均值的1.2倍或绝对阈值8%的较小值）
        if len(df) >= 20:
            # 计算20周期ATR均值
            atr_mean = df['atr_pct'].rolling(window=20, min_periods=10).mean()
            # 相对阈值：ATR均值的1.2倍，但不低于2%或高于绝对阈值
            relative_threshold = np.minimum(atr_mean * 1.2, self.config.max_atr_pct)
            # 确保相对阈值至少为2%（避免过度宽松）
            min_atr_threshold = 0.02
            effective_threshold = np.maximum(relative_threshold, min_atr_threshold)
            volatility_filter = df['atr_pct'] > effective_threshold
        else:
            # 数据不足时使用绝对阈值
            volatility_filter = df['atr_pct'] > self.config.max_atr_pct
        
        df.loc[volatility_filter, 'signal'] = 'hold'
        
        # 成交量确认
        df.loc[df['volume_ratio'] < self.config.min_volume_ratio, 'signal'] = 'hold'
        
        # 趋势确认（连续3周期）
        for i in range(len(df) - self.config.trend_confirmation_period + 1):
            window = df.iloc[i:i+self.config.trend_confirmation_period]
            if len(window) == self.config.trend_confirmation_period:
                current_signal = window.iloc[-1]['signal']
                if current_signal != 'hold':
                    # 检查前几个周期是否一致
                    signal_count = (window['signal'] == current_signal).sum()
                    if signal_count < self.config.trend_confirmation_period:
                        df.iloc[i+self.config.trend_confirmation_period-1, df.columns.get_loc('signal')] = 'hold'
        
        # 计算最终统计
        final_signals = (df['signal'] != 'hold').sum()
        final_long = (df['signal'] == 'long').sum()
        final_short = (df['signal'] == 'short').sum()
        
        # 记录过滤效果
        if original_signals > 0:
            filtered_pct = (original_signals - final_signals) / original_signals * 100
            self.logger.info(
                f"信号过滤: 原始{original_signals}个(多{original_long}/空{original_short}) → "
                f"剩余{final_signals}个(多{final_long}/空{final_short}), "
                f"过滤{strength_filtered_count}个强度<{threshold}信号, 过滤率{filtered_pct:.1f}%"
            )
        else:
            self.logger.debug("无原始信号需要过滤")
        
        return df
    
    def _calculate_position_size(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算动态仓位大小 - 优化版，支持信号强度指数调整"""
        df['position_size'] = 0.0
        
        # 基础仓位
        base_size = self.config.base_position_size_pct
        
        for idx, row in df.iterrows():
            if row['signal'] in ['long', 'short'] and row['signal_strength'] > 0:
                # 1. 信号强度调整（核心优化）
                if self.config.position_size_by_strength:
                    # 使用指数调整：信号强度对仓位的影响非线性
                    # 强度为0-100，除以100得到0-1的比例
                    strength_ratio = row['signal_strength'] / 100
                    # 应用指数：strength_to_position_power通常>1，表示信号越强仓位增加越快
                    strength_multiplier = 0.3 + strength_ratio ** self.config.strength_to_position_power * 1.7
                    # 结果范围：0.3-2.0（当strength_to_position_power=1.5时，强度100分→约2.0倍）
                    self.logger.debug(f"动态仓位调整: 强度{row['signal_strength']:.1f} → 乘数{strength_multiplier:.2f}")
                else:
                    # 旧逻辑：线性调整（0.5-1.5倍）
                    strength_multiplier = 0.5 + row['signal_strength'] / 100
                
                # 2. ATR调整（高波动时减少仓位）
                atr_multiplier = 1.0
                if self.config.atr_position_adjust:
                    atr_multiplier = max(0.5, min(1.5, 0.03 / max(0.01, row['atr_pct'])))
                    self.logger.debug(f"ATR调整: ATR%={row['atr_pct']:.3%} → 乘数{atr_multiplier:.2f}")
                
                # 3. 综合仓位
                position_size = base_size * strength_multiplier * atr_multiplier
                
                # 4. 限制范围
                position_size = max(
                    self.config.min_position_size_pct,
                    min(self.config.max_position_size_pct, position_size)
                )
                
                df.at[idx, 'position_size'] = position_size
                
                # 记录仓位调整详情
                if position_size > base_size * 1.2:
                    self.logger.info(f"强信号仓位增加: 基础{base_size*100:.1f}% → {position_size*100:.1f}% (强度{row['signal_strength']:.1f})")
                elif position_size < base_size * 0.8:
                    self.logger.info(f"弱信号仓位减少: 基础{base_size*100:.1f}% → {position_size*100:.1f}% (强度{row['signal_strength']:.1f})")
        
        return df
    
    def get_current_signal(self, df: pd.DataFrame) -> Tuple[str, float, float]:
        """获取最新信号"""
        if len(df) == 0:
            return 'hold', 0, 0
        
        latest = df.iloc[-1]
        signal = latest.get('signal', 'hold')
        strength = latest.get('signal_strength', 0)
        position_size = latest.get('position_size', 0)
        
        return signal, strength, position_size


# ==================== 交易系统（修复版） ====================
class FixedTradingSystem:
    """修复交易系统 - 解决51010错误"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 初始化交易所（修复版本）
        self.exchange = ccxt.okx({
            'apiKey': config.api_key,
            'secret': config.api_secret,
            'password': config.api_password,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'sandbox': config.testnet,
                'defaultMarginMode': config.margin_mode,
            }
        })
        
        # 初始化信号生成器（传递exchange以支持多时间框架数据获取）
        self.signal_generator = OptimizedSignalGenerator(config, self.exchange)
        
        # 初始化ML数据收集器
        self.ml_collector = None
        if config.ml_signal_scoring:
            try:
                # 获取数据目录
                data_dir = getattr(config, 'ml_data_dir', 'ml_data')
                self.ml_collector = ml_data_collector.MLDataCollector(config, data_dir)
                self.logger.info(f"ML数据收集器初始化完成，数据目录: {data_dir}")
            except Exception as e:
                self.logger.error(f"初始化ML数据收集器失败: {e}")
        # 状态变量
        self.is_running = True
        self.position = None
        self.position_type = None  # 'long' or 'short'
        self.position_entry_price = 0
        
        # 舆情分析
        self.last_sentiment_fetch_time = 0
        self.current_sentiment_score = 0.0  # -1 到 +1，负值为看空，正值为看多
        
        # 移动止损跟踪
        self.position_highest_price = 0  # 做多时的最高价
        self.position_lowest_price = 0   # 做空时的最低价
        self.trailing_stop_triggered = False  # 移动止损是否已触发
        
        # 移动止盈跟踪
        self.trailing_takeprofit_triggered = False  # 移动止盈是否已触发
        self.trailing_takeprofit_best_price = 0  # 移动止盈期间的最佳价格
        
        # 统计
        self.trade_stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'long_trades': 0,
            'short_trades': 0,
            'total_profit': 0,
            'total_loss': 0,
        }
        
        # 每日统计
        self.today_trades = 0
        self.today_profit = 0
        self.today_loss = 0
        self.last_trade_time = None
        self.consecutive_losses = 0
        
        self.logger.info("OKX末日战车修复版交易系统初始化完成")
        self.logger.info(f"交易对: {config.symbol}, 杠杆: {config.leverage}x")
        self.logger.info(f"动态仓位: {config.base_position_size_pct*100:.1f}%-{config.max_position_size_pct*100:.1f}%")
        self.logger.info(f"做空侧重: {config.short_bias*100:.1f}%, 测试网: {config.testnet}")
        if config.use_simple_orders:
            self.logger.info("使用简单订单模式（后设置止损止盈）")
    
    def set_leverage(self):
        """设置杠杆"""
        try:
            # OKX设置杠杆
            self.exchange.set_leverage(
                leverage=self.config.leverage,
                symbol=self.config.symbol
            )
            self.logger.info(f"设置杠杆: {self.config.leverage}x")
        except Exception as e:
            self.logger.warning(f"设置杠杆失败（可能已设置）: {e}")
    
    def fetch_sentiment_score(self) -> float:
        """
        获取舆情分数 - Fear & Greed Index
        返回: -1 (极端看空) 到 +1 (极端看多)
        数据源: https://api.alternative.me/fng/
        """
        try:
            # 获取Fear & Greed Index
            response = requests.get('https://api.alternative.me/fng/', timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 解析数据
            if 'data' in data and len(data['data']) > 0:
                value_str = data['data'][0].get('value', '50')
                classification = data['data'][0].get('value_classification', 'Neutral')
                
                try:
                    value = int(value_str)
                except ValueError:
                    value = 50  # 默认中性
                
                # 将0-100转换为-1到+1（50=0, 100=+1, 0=-1）
                sentiment = (value - 50) / 50.0
                # 确保在范围内
                sentiment = max(-1.0, min(1.0, sentiment))
                
                self.logger.info(f"Fear & Greed Index: {value} ({classification}), 舆情分数: {sentiment:.2f}")
                return sentiment
            else:
                self.logger.warning("Fear & Greed Index API返回数据格式异常")
                return 0.0
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"获取Fear & Greed Index失败: {e}")
            return 0.0
        except (KeyError, ValueError, IndexError) as e:
            self.logger.error(f"解析Fear & Greed Index数据失败: {e}")
            return 0.0
    
    def update_sentiment_if_needed(self):
        """检查是否需要更新舆情分数（每10分钟更新一次）"""
        current_time = time.time()
        if current_time - self.last_sentiment_fetch_time > 600:  # 10分钟
            sentiment_score = self.fetch_sentiment_score()
            self.current_sentiment_score = sentiment_score
            self.signal_generator.update_sentiment_bias(sentiment_score)
            self.last_sentiment_fetch_time = current_time
    
    def fetch_ohlcv(self, limit: int = 200) -> pd.DataFrame:
        """获取K线数据"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(
                self.config.symbol,
                timeframe=self.config.timeframe,
                limit=limit
            )
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            self.logger.error(f"获取K线数据失败: {e}")
            return pd.DataFrame()
    
    def fetch_position(self):
        """获取当前持仓"""
        try:
            # 获取市场信息以规范化symbol
            market = self.exchange.market(self.config.symbol)
            market_symbol = market['symbol']  # 规范化后的symbol
            
            positions = self.exchange.fetch_positions([self.config.symbol])
            self.logger.info(f"获取持仓: {len(positions)}个仓位，目标symbol: {self.config.symbol} -> {market_symbol}")
            
            valid_positions = []
            for pos in positions:
                pos_symbol = pos.get('symbol', '')
                contracts = float(pos.get('contracts', 0))
                side = pos.get('side', '')
                entry_price = pos.get('entryPrice', 0)
                
                self.logger.info(f"仓位: {pos_symbol}, 方向: {side}, 合约: {contracts}, 均价: {entry_price}")
                
                # 检查symbol是否匹配（支持多种格式）
                if (pos_symbol == market_symbol or pos_symbol == self.config.symbol) and abs(contracts) > 0.001:
                    valid_positions.append(pos)
            
            if valid_positions:
                # 取第一个有效仓位（通常只有一个）
                pos = valid_positions[0]
                contracts = float(pos.get('contracts', 0))
                side = pos.get('side', '')
                
                self.position = pos
                self.position_type = 'long' if side == 'long' else 'short'
                self.position_entry_price = float(pos.get('entryPrice', 0))
                contract_size = float(pos.get('contractSize', 0.1))
                eth_amount = contracts * contract_size
                
                # 初始化移动止损跟踪（如果是第一次检测到这个持仓）
                if self.position_highest_price == 0 and self.position_lowest_price == 0:
                    if self.position_type == 'long':
                        self.position_highest_price = self.position_entry_price
                        self.position_lowest_price = 0
                    else:
                        self.position_lowest_price = self.position_entry_price
                        self.position_highest_price = 0
                    self.trailing_stop_triggered = False
                    self.logger.info(f"移动止损跟踪初始化: {self.position_type}, 初始价={self.position_entry_price:.2f}")
                
                self.logger.info(f"检测到有效持仓: {self.position_type}, 合约: {contracts}, ETH数量: {eth_amount:.4f}, 均价: {self.position_entry_price}")
                self.logger.info(f"持仓价值: ${pos.get('notional', 0):.2f}, 未实现盈亏: ${pos.get('unrealizedPnl', 0):.2f}")
                return
            
            # 无持仓
            self.logger.info("未检测到有效持仓")
            self.position = None
            self.position_type = None
            self.position_entry_price = 0
            self.position_highest_price = 0
            self.position_lowest_price = 0
            self.trailing_stop_triggered = False
            
        except Exception as e:
            self.logger.error(f"获取持仓失败: {e}")
    
    def calculate_dynamic_stop_loss_take_profit(self, current_price: float, signal_type: str, atr_value: float = None, trend_direction: int = 0) -> Tuple[float, float]:
        """计算动态止损止盈价格（优化版：支持波动率和趋势调整）"""
        # 基础百分比止损止盈
        base_stop_loss_pct = self.config.base_stoploss_pct
        base_take_profit_pct = self.config.base_takeprofit_pct
        
        # 如果提供了ATR值，使用ATR动态调整
        if atr_value and atr_value > 0:
            # ATR止损止盈距离
            atr_stop_loss_distance = atr_value * self.config.atr_stoploss_multiplier
            atr_take_profit_distance = atr_value * self.config.atr_takeprofit_multiplier
            
            # 转换为百分比
            atr_stop_loss_pct = atr_stop_loss_distance / current_price
            atr_take_profit_pct = atr_take_profit_distance / current_price
            
            # 使用ATR和基础百分比中的较大值（更保守）
            stop_loss_pct = max(base_stop_loss_pct, atr_stop_loss_pct)
            take_profit_pct = max(base_take_profit_pct, atr_take_profit_pct)
            
            # 波动率调整（优化点5）
            if self.config.stop_loss_volatility_adjust:
                # 计算波动率（ATR百分比）
                volatility_pct = atr_value / current_price
                # 高波动时增加止损距离：波动率>2%时增加止损
                if volatility_pct > 0.02:
                    volatility_multiplier = self.config.volatility_stop_multiplier
                    stop_loss_pct = stop_loss_pct * volatility_multiplier
                    self.logger.info(f"高波动调整: 波动率{volatility_pct:.2%} > 2%，止损增加{volatility_multiplier}倍 → {stop_loss_pct:.2%}")
            
            # 趋势调整（优化点5）
            if self.config.stop_loss_trend_adjust and trend_direction != 0:
                # trend_direction: 1=上升趋势, -1=下降趋势, 0=无趋势
                # 顺趋势放宽止损：如果信号方向与趋势一致，放宽止损
                if (signal_type == 'long' and trend_direction > 0) or (signal_type == 'short' and trend_direction < 0):
                    trend_multiplier = self.config.trend_stop_multiplier
                    stop_loss_pct = stop_loss_pct * trend_multiplier
                    self.logger.info(f"顺趋势调整: 信号{signal_type}, 趋势{trend_direction}，止损放宽{trend_multiplier}倍 → {stop_loss_pct:.2%}")
                # 逆趋势收紧止损：如果信号方向与趋势相反，收紧止损（可选，暂不实现）
            
            self.logger.info(f"ATR动态风控: ATR={atr_value:.4f}, 止损距离={atr_stop_loss_distance:.2f}({atr_stop_loss_pct:.2%}), 止盈距离={atr_take_profit_distance:.2f}({atr_take_profit_pct:.2%})")
        else:
            # 无ATR数据，使用基础百分比
            stop_loss_pct = base_stop_loss_pct
            take_profit_pct = base_take_profit_pct
        
        # 确保止损止盈在合理范围内
        stop_loss_pct = min(max(stop_loss_pct, 0.01), 0.50)  # 限制在1%-50%之间
        take_profit_pct = min(max(take_profit_pct, 0.01), 0.50)
        
        # 计算价格
        if signal_type == 'long':
            # 做多：止损价低于当前价，止盈价高于当前价
            stop_loss_price = current_price * (1 - stop_loss_pct)
            take_profit_price = current_price * (1 + take_profit_pct)
        else:
            # 做空：止损价高于当前价，止盈价低于当前价
            stop_loss_price = current_price * (1 + stop_loss_pct)
            take_profit_price = current_price * (1 - take_profit_pct)
        
        # 计算盈亏比
        risk_reward_ratio = take_profit_pct / stop_loss_pct if stop_loss_pct > 0 else 0
        
        self.logger.info(f"风控价格: {signal_type} 止损={stop_loss_price:.2f}({stop_loss_pct:.2%}), 止盈={take_profit_price:.2f}({take_profit_pct:.2%}), 盈亏比={risk_reward_ratio:.2f}:1")
        
        return stop_loss_price, take_profit_price
    
    def place_order_simple(self, order_type: str, position_size: float, 
                          current_price: float, signal_type: str) -> bool:
        """简单下单（修复51010错误）"""
        try:
            # 最小下单数量检查
            market = self.exchange.market(self.config.symbol)
            min_amount = market['limits']['amount']['min']
            
            if position_size < min_amount:
                self.logger.warning(f"下单数量{position_size}小于最小数量{min_amount}，调整为{min_amount}")
                position_size = min_amount
            
            # 简单下单参数（修复51010错误的关键）
            order_params = {
                'symbol': self.config.symbol,
                'type': 'market',
                'side': order_type,
                'amount': position_size,
                'params': {
                    'tdMode': self.config.td_mode,  # 明确指定交易模式
                    'posSide': 'long' if signal_type == 'long' else 'short',
                }
            }
            
            self.logger.info(f"下单参数: {order_params}")
            
            # 下单
            order = self.exchange.create_order(**order_params)
            self.logger.info(f"下单成功: {order_type} {position_size} {self.config.symbol}")
            self.logger.info(f"订单ID: {order.get('id', 'N/A')}")
            
            # 后设置止损止盈（TODO: 传递ATR和趋势数据）
            if order.get('id'):
                self.set_stop_loss_take_profit(
                    order['id'], current_price, signal_type, None, 0
                )
            
            return True
            
        except Exception as e:
            self.logger.error(f"下单失败: {e}")
            return False
    
    def set_stop_loss_take_profit(self, order_id: str, current_price: float, signal_type: str, atr_value: float = None, trend_direction: int = 0):
        """后设置止损止盈（支持趋势优化）"""
        try:
            # 计算止损止盈价格（支持ATR动态调整和趋势优化）
            stop_loss_price, take_profit_price = self.calculate_dynamic_stop_loss_take_profit(
                current_price, signal_type, atr_value, trend_direction
            )
            
            self.logger.info(f"后设置止损止盈: {signal_type} 止损={stop_loss_price:.2f}, 止盈={take_profit_price:.2f}")
            
            # 初始化移动止损跟踪
            if signal_type == 'long':
                self.position_highest_price = current_price
                self.position_lowest_price = 0
            else:
                self.position_lowest_price = current_price
                self.position_highest_price = 0
            self.trailing_stop_triggered = False
            
            # 初始化移动止盈跟踪
            self.trailing_takeprofit_triggered = False
            self.trailing_takeprofit_best_price = 0
            
            self.logger.info(f"移动止损/止盈初始化: {signal_type} 初始价={current_price:.2f}")
            
            # 这里可以添加设置止损止盈的逻辑
            # 由于时间关系，暂时记录日志，实际交易中需要实现
            
        except Exception as e:
            self.logger.warning(f"设置止损止盈失败: {e}")
    
    def place_order(self, order_type: str, position_size: float, 
                    current_price: float, signal_type: str) -> bool:
        """下单（主入口）"""
        if not self.config.enable_trading:
            self.logger.info(f"模拟交易: {order_type} {position_size} {self.config.symbol} @ {current_price}")
            return True
        
        # 使用简单订单模式（修复51010错误）
        return self.place_order_simple(order_type, position_size, current_price, signal_type)
    
    def close_position(self, reason: str = 'signal') -> bool:
        # 在平仓前收集交易数据（如果ML收集器已启用）
        if self.ml_collector is not None and self.position is not None:
            try:
                # 计算持仓时间
                if self.position_entry_time:
                    duration_minutes = (datetime.now() - self.position_entry_time).total_seconds() / 60
                else:
                    duration_minutes = 0
                
                # 获取当前价格
                current_price = self.get_current_price()
                if current_price > 0 and self.position_entry_price > 0:
                    if self.position_type == 'long':
                        pnl_pct = (current_price - self.position_entry_price) / self.position_entry_price
                    else:
                        pnl_pct = (self.position_entry_price - current_price) / self.position_entry_price
                    
                    # 收集交易数据
                    trade_info = {
                        'id': f"trade_{self.trade_stats['total_trades']}",
                        'position_type': self.position_type,
                        'entry_price': self.position_entry_price,
                        'exit_price': current_price,
                        'entry_time': self.position_entry_time.isoformat() if hasattr(self, 'position_entry_time') else '',
                        'exit_time': datetime.now().isoformat(),
                        'position_size': abs(self.position),
                        'pnl_pct': pnl_pct,
                        'pnl_amount': pnl_pct * abs(self.position) * self.position_entry_price,
                        'duration_minutes': duration_minutes,
                        'exit_reason': reason,
                        'signal_strength': self.last_signal_strength if hasattr(self, 'last_signal_strength') else 0,
                        'stop_loss_pct': self.config.base_stoploss_pct,
                        'take_profit_pct': self.config.base_takeprofit_pct,
                        'volatility_atr': self.last_atr if hasattr(self, 'last_atr') else 0,
                        'trend_direction': self.last_trend if hasattr(self, 'last_trend') else 0,
                        'sentiment_score': self.current_sentiment_score,
                    }
                    self.ml_collector.collect_trade_data(trade_info)
            except Exception as e:
                self.logger.error(f"收集交易数据失败: {e}")
        """平仓"""
        if self.position is None:
            self.logger.info("无持仓可平")
            return False
        
        try:
            # 获取当前持仓方向
            if self.position_type == 'long':
                side = 'sell'
            else:
                side = 'buy'
            
            # 获取持仓数量
            position_size = abs(float(self.position.get('contracts', 0)))
            
            if position_size <= 0.001:
                self.logger.info("持仓数量过小，无需平仓")
                return False
            
            # 平仓参数（使用简单模式）
            order_params = {
                'symbol': self.config.symbol,
                'type': 'market',
                'side': side,
                'amount': position_size,
                'params': {
                    'tdMode': self.config.td_mode,
                    'posSide': self.position_type,  # 持仓方向
                }
            }
            
            # 平仓
            order = self.exchange.create_order(**order_params)
            
            # 计算盈亏
            current_price = float(self.position.get('markPrice', 0))
            entry_price = self.position_entry_price
            
            if self.position_type == 'long':
                pnl_pct = (current_price - entry_price) / entry_price * 100
            else:
                pnl_pct = (entry_price - current_price) / entry_price * 100
            
            # 更新统计
            self.trade_stats['total_trades'] += 1
            if self.position_type == 'long':
                self.trade_stats['long_trades'] += 1
            else:
                self.trade_stats['short_trades'] += 1
            
            if pnl_pct > 0:
                self.trade_stats['winning_trades'] += 1
                self.trade_stats['total_profit'] += abs(pnl_pct)
                self.consecutive_losses = 0
                self.logger.info(f"平仓盈利: {pnl_pct:.2f}%")
            else:
                self.trade_stats['losing_trades'] += 1
                self.trade_stats['total_loss'] += abs(pnl_pct)
                self.consecutive_losses += 1
                self.logger.warning(f"平仓亏损: {pnl_pct:.2f}%")
            
            # 重置持仓
            self.position = None
            self.position_type = None
            self.position_entry_price = 0
            
            # 重置移动止损和移动止盈状态
            self.position_highest_price = 0
            self.position_lowest_price = 0
            self.trailing_stop_triggered = False
            self.trailing_takeprofit_triggered = False
            self.trailing_takeprofit_best_price = 0
            
            self.logger.info(f"平仓成功: {reason}")
            return True
            
        except Exception as e:
            self.logger.error(f"平仓失败: {e}")
            return False
    
    def calculate_position_size(self, current_price: float) -> float:
        """计算仓位大小"""
        try:
            # 获取账户余额
            balance = self.exchange.fetch_balance()
            usdt_total_1 = balance['total'].get('USDT', 0) if 'total' in balance else 0
            usdt_total_2 = balance['USDT']['total'] if 'USDT' in balance else 0
            
            self.logger.info(f"余额检查: total['USDT']={usdt_total_1}, balance['USDT']['total']={usdt_total_2}")
            
            # 使用total['USDT']，这是ccxt标准方式
            usdt_balance = usdt_total_1
            
            # 使用基础仓位比例
            position_value = usdt_balance * self.config.base_position_size_pct
            self.logger.info(f"仓位计算: 总余额={usdt_balance} USDT, {self.config.base_position_size_pct*100:.1f}% = {position_value:.2f} USDT")
            
            # 获取市场信息
            market = self.exchange.market(self.config.symbol)
            contract_size = market.get('contractSize', 0.1)
            
            # 转换为合约数量
            # position_value / current_price = ETH数量
            # ETH数量 / contract_size = 合约数量
            eth_amount = position_value / current_price
            contract_amount = eth_amount / contract_size
            
            self.logger.info(f"合约计算: ETH价格={current_price}, 合约乘数={contract_size}")
            self.logger.info(f"          ETH数量={eth_amount:.4f}, 合约数量={contract_amount:.4f}")
            
            # 确保满足最小下单数量
            min_amount = market['limits']['amount']['min']
            
            if contract_amount < min_amount:
                self.logger.warning(f"计算仓位{contract_amount}小于最小数量{min_amount}，调整为{min_amount}")
                return min_amount
            
            return contract_amount
            
        except Exception as e:
            self.logger.error(f"计算仓位失败: {e}")
            return 0
    
    def check_stop_loss_take_profit(self, current_price: float, atr_value: float = None, trend_direction: int = 0) -> Optional[str]:
        """检查止损止盈（增强版：支持移动止损和ATR动态止损）"""
        if self.position is None:
            return None
        
        entry_price = self.position_entry_price
        
        # 更新最高价/最低价（用于移动止损）
        if self.position_type == 'long':
            # 做多：更新最高价
            if current_price > self.position_highest_price or self.position_highest_price == 0:
                self.position_highest_price = current_price
                self.logger.debug(f"更新做多最高价: {current_price:.2f}")
        else:
            # 做空：更新最低价
            if current_price < self.position_lowest_price or self.position_lowest_price == 0:
                self.position_lowest_price = current_price
                self.logger.debug(f"更新做空最低价: {current_price:.2f}")
        
        # 计算动态止损止盈价格（使用ATR如果可用，支持趋势调整）
        stop_loss_price, take_profit_price = self.calculate_dynamic_stop_loss_take_profit(
            entry_price, self.position_type, atr_value, trend_direction
        )
        
        # 检查基础止损止盈
        if self.position_type == 'long':
            if current_price <= stop_loss_price:
                return '基础止损'
            elif current_price >= take_profit_price:
                return '基础止盈'
        else:
            if current_price >= stop_loss_price:
                return '基础止损'
            elif current_price <= take_profit_price:
                return '基础止盈'
        
        # 检查移动止损（如果配置了且未触发）
        if self.config.trailing_stop_pct > 0 and not self.trailing_stop_triggered:
            if self.position_type == 'long':
                # 做多移动止损：从最高价下跌trailing_stop_pct%
                trailing_stop_price = self.position_highest_price * (1 - self.config.trailing_stop_pct)
                if current_price <= trailing_stop_price and current_price > entry_price * (1 - self.config.base_stoploss_pct):
                    self.trailing_stop_triggered = True
                    self.logger.info(f"触发移动止损: 最高价={self.position_highest_price:.2f}, 移动止损价={trailing_stop_price:.2f}")
                    return '移动止损'
            else:
                # 做空移动止损：从最低价上涨trailing_stop_pct%
                trailing_stop_price = self.position_lowest_price * (1 + self.config.trailing_stop_pct)
                if current_price >= trailing_stop_price and current_price < entry_price * (1 + self.config.base_stoploss_pct):
                    self.trailing_stop_triggered = True
                    self.logger.info(f"触发移动止损: 最低价={self.position_lowest_price:.2f}, 移动止损价={trailing_stop_price:.2f}")
                    return '移动止损'
        
        # 检查移动止盈（如果配置了）
        if self.config.trailing_takeprofit_trigger_pct > 0:
            # 计算当前盈利百分比
            if self.position_type == 'long':
                profit_pct = (current_price - entry_price) / entry_price
                best_price = self.position_highest_price
            else:
                profit_pct = (entry_price - current_price) / entry_price
                best_price = self.position_lowest_price
            
            # 检查是否达到移动止盈触发阈值
            if not self.trailing_takeprofit_triggered:
                if profit_pct >= self.config.trailing_takeprofit_trigger_pct:
                    self.trailing_takeprofit_triggered = True
                    self.trailing_takeprofit_best_price = current_price
                    self.logger.info(f"移动止盈触发: 盈利{profit_pct:.2%} ≥ 触发阈值{self.config.trailing_takeprofit_trigger_pct:.2%}，开始跟踪")
            else:
                # 移动止盈已触发，更新最佳价格
                if self.position_type == 'long':
                    if current_price > self.trailing_takeprofit_best_price:
                        self.trailing_takeprofit_best_price = current_price
                        self.logger.debug(f"更新移动止盈最佳价: {current_price:.2f}")
                else:
                    if current_price < self.trailing_takeprofit_best_price:
                        self.trailing_takeprofit_best_price = current_price
                        self.logger.debug(f"更新移动止盈最佳价: {current_price:.2f}")
                
                # 检查是否触发移动止盈
                if self.position_type == 'long':
                    # 做多移动止盈：从最佳价下跌trailing_takeprofit_pct%
                    trailing_takeprofit_price = self.trailing_takeprofit_best_price * (1 - self.config.trailing_takeprofit_pct)
                    if current_price <= trailing_takeprofit_price:
                        self.logger.info(f"触发移动止盈: 最佳价={self.trailing_takeprofit_best_price:.2f}, 移动止盈价={trailing_takeprofit_price:.2f}")
                        return '移动止盈'
                else:
                    # 做空移动止盈：从最佳价上涨trailing_takeprofit_pct%
                    trailing_takeprofit_price = self.trailing_takeprofit_best_price * (1 + self.config.trailing_takeprofit_pct)
                    if current_price >= trailing_takeprofit_price:
                        self.logger.info(f"触发移动止盈: 最佳价={self.trailing_takeprofit_best_price:.2f}, 移动止盈价={trailing_takeprofit_price:.2f}")
                        return '移动止盈'
        
        return None
    
    def check_daily_limits(self) -> bool:
        """检查每日限制"""
        # 每日交易次数限制
        if self.today_trades >= self.config.max_daily_trades:
            self.logger.warning(f"达到每日最大交易次数限制: {self.today_trades}/{self.config.max_daily_trades}")
            return False
        
        # 每日亏损限制
        daily_loss_pct = (self.today_loss - self.today_profit) / 100  # 简化计算
        if daily_loss_pct >= self.config.max_daily_loss_pct:
            self.logger.warning(f"达到每日最大亏损限制: {daily_loss_pct:.1%}/{self.config.max_daily_loss_pct:.1%}")
            return False
        
        # 连续亏损冷却
        if self.consecutive_losses >= 3:
            self.logger.warning(f"连续亏损{self.consecutive_losses}次，进入冷却期")
            time.sleep(self.config.cooling_period_minutes * 60)
            self.consecutive_losses = 0
        
        return True
    
    def reset_daily_stats(self):
        """重置每日统计"""
        now = datetime.now()
        if self.last_trade_time is None or (now - self.last_trade_time).days >= 1:
            self.today_trades = 0
            self.today_profit = 0
            self.today_loss = 0
            self.logger.info("新的一天，重置每日统计")
    
    def print_stats(self):
        """打印统计信息"""
        total_trades = self.trade_stats['total_trades']
        if total_trades > 0:
            win_rate = self.trade_stats['winning_trades'] / total_trades * 100
            avg_profit = self.trade_stats['total_profit'] / self.trade_stats['winning_trades'] if self.trade_stats['winning_trades'] > 0 else 0
            avg_loss = self.trade_stats['total_loss'] / self.trade_stats['losing_trades'] if self.trade_stats['losing_trades'] > 0 else 0
            
            self.logger.info(f"📊 交易统计: {total_trades}次交易, 胜率: {win_rate:.1f}%")
            self.logger.info(f"   平均盈利: {avg_profit:.1f}%, 平均亏损: {avg_loss:.1f}%")
            self.logger.info(f"   今日交易: {self.today_trades}次, 连续亏损: {self.consecutive_losses}次")
        else:
            self.logger.info("📊 尚无交易记录")
    
    def run(self):
        """运行交易系统"""
        self.logger.info("开始运行交易系统...")
        
        # 设置杠杆
        self.set_leverage()
        
        # 主循环
        while self.is_running:
            try:
                self.logger.debug("交易循环开始")
                # 重置每日统计
                self.reset_daily_stats()
                
                # 检查每日限制
                if not self.check_daily_limits():
                    break
                
                # 获取市场数据
                df = self.fetch_ohlcv(limit=200)
                if len(df) < 100:
                    self.logger.warning("市场数据不足，等待重试...")
                    time.sleep(self.config.check_interval)
                    continue
                
                # 更新舆情分析（每10分钟更新一次）
                self.update_sentiment_if_needed()
                
                # 获取当前持仓
                self.fetch_position()
                
                # 计算信号
                df = self.signal_generator.calculate_signals(df)
                signal, signal_strength, position_size_pct = self.signal_generator.get_current_signal(df)
                
                # 获取当前价格
                current_price = df['close'].iloc[-1]
                
                # 检查止损止盈（使用ATR动态调整和趋势优化）
                atr_value = df['atr'].iloc[-1] if 'atr' in df.columns else None
                # 获取趋势方向（TODO: 从更高时间框架数据获取）
                trend_direction = 0  # 默认无趋势，可从higher_timeframe_data获取
                stop_take_reason = self.check_stop_loss_take_profit(current_price, atr_value, trend_direction)
                if stop_take_reason is not None:
                    self.logger.info(f"触发{stop_take_reason}，执行平仓")
                    self.close_position(stop_take_reason)
                    time.sleep(self.config.check_interval)
                    continue
                
                # 处理交易信号（强度阈值从>0提高到>15，避免低质量信号）
                if signal != 'hold' and signal_strength > 15:
                    # 检查是否已有持仓
                    if self.position is not None:
                        # 已有持仓，检查是否需要反向开仓
                        if self.position_type != signal:
                            self.logger.info(f"已有{self.position_type}持仓，收到反向{signal}信号，先平仓")
                            self.close_position('reverse_signal')
                            time.sleep(2)  # 等待平仓完成
                    
                    # 开新仓
                    if self.position is None:
                        self.logger.info(f"收到{signal}信号，强度: {signal_strength:.1f}，仓位比例: {position_size_pct*100:.1f}%")
                        
                        # 计算仓位大小
                        position_size = self.calculate_position_size(current_price)
                        
                        if position_size > 0:
                            # 下单
                            order_type = 'buy' if signal == 'long' else 'sell'
                            success = self.place_order(order_type, position_size, current_price, signal)
                            
                            if success:
                                self.today_trades += 1
                                self.last_trade_time = datetime.now()
                                
                                # 更新持仓状态
                                self.position_type = signal
                                self.position_entry_price = current_price
                                
                                self.logger.info(f"开仓成功: {signal} {position_size} {self.config.symbol}")
                
                # 打印统计信息（每10分钟一次）
                if int(time.time()) % 600 < self.config.check_interval:
                    self.print_stats()
                
                # 等待下一次检查
                self.logger.debug(f"循环完成，等待{self.config.check_interval}秒")
                time.sleep(self.config.check_interval)
                
            except KeyboardInterrupt:
                self.logger.info("用户中断程序")
                self.is_running = False
                break
                
            except Exception as e:
                self.logger.error(f"交易循环异常: {e}", exc_info=True)
                time.sleep(self.config.check_interval * 2)
        
        # 程序结束前平仓
        if self.position is not None:
            self.logger.info("程序结束，平仓现有持仓")
            self.close_position('shutdown')
        
        # 打印最终统计
        self.print_stats()
        self.logger.info("交易系统停止")


# ==================== 配置加载（优化版） ====================
def load_config() -> Config:
    """加载配置文件（优化版）"""
    # 优先使用优化配置文件
    config_file = 'config_optimized_v2.ini'
    if not os.path.exists(config_file):
        config_file = 'config_fixed_v2.ini'
        if not os.path.exists(config_file):
            config_file = 'config.ini'
            if not os.path.exists(config_file):
                raise FileNotFoundError(f"配置文件不存在: {config_file}")
    
    print(f"📂 使用配置文件: {config_file}")
    if 'optimized' in config_file:
        print("✅ 使用优化版配置文件（包含6个优化点）")
    elif 'fixed' in config_file:
        print("⚠️  使用修复版配置文件（部分优化参数使用默认值）")
    else:
        print("⚠️  使用基础配置文件（优化参数使用默认值）")
    
    config = configparser.ConfigParser()
    config.read(config_file)
    
    # 读取信号强度权重JSON字符串
    signal_strength_weights_json = config.get('Optimization', 'signal_strength_weights', 
        fallback='{"momentum": 0.15, "volume": 0.10, "rsi": 0.15, "trend": 0.20, "bb": 0.10, "volatility": 0.10, "multi_timeframe": 0.10, "sentiment": 0.10}')
    
    return Config(
        # OKX API配置
        api_key=config.get('OKX', 'api_key', fallback=''),
        api_secret=config.get('OKX', 'api_secret', fallback=''),
        api_password=config.get('OKX', 'api_password', fallback=''),
        
        # 交易对
        symbol=config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP'),
        
        # 杠杆设置
        leverage=int(config.get('Trading', 'leverage', fallback='10')),
        margin_mode=config.get('Trading', 'margin_mode', fallback='cross'),
        
        # 交易模式（修复参数）
        td_mode=config.get('System', 'td_mode', fallback='cross'),
        
        # 动态仓位管理
        base_position_size_pct=float(config.get('Trading', 'base_position_size_pct', fallback='0.10')),
        max_position_size_pct=float(config.get('Trading', 'max_position_size_pct', fallback='0.20')),
        min_position_size_pct=float(config.get('Trading', 'min_position_size_pct', fallback='0.03')),
        atr_position_adjust=config.getboolean('Trading', 'atr_position_adjust', fallback=True),
        
        # 交易限制
        max_daily_trades=int(config.get('Trading', 'max_daily_trades', fallback='15')),
        max_daily_loss_pct=float(config.get('Trading', 'max_daily_loss_pct', fallback='0.25')),
        max_total_loss_pct=float(config.get('Trading', 'max_total_loss_pct', fallback='0.40')),
        cooling_period_minutes=int(config.get('Trading', 'cooling_period_minutes', fallback='5')),
        
        # 策略参数
        timeframe=config.get('Strategy', 'timeframe', fallback='5m'),
        momentum_period=int(config.get('Strategy', 'momentum_period', fallback='5')),
        momentum_threshold_long=float(config.get('Strategy', 'momentum_threshold_long', fallback='0.005')),
        momentum_threshold_short=float(config.get('Strategy', 'momentum_threshold_short', fallback='-0.005')),
        rsi_period=int(config.get('Strategy', 'rsi_period', fallback='7')),
        rsi_overbought=int(config.get('Strategy', 'rsi_overbought', fallback='75')),
        rsi_oversold=int(config.get('Strategy', 'rsi_oversold', fallback='25')),
        short_bias=float(config.get('Strategy', 'short_bias', fallback='0.75')),
        
        # 动态止损止盈
        base_stoploss_pct=float(config.get('Risk', 'base_stoploss_pct', fallback='0.20')),
        base_takeprofit_pct=float(config.get('Risk', 'base_takeprofit_pct', fallback='0.25')),
        atr_stoploss_multiplier=float(config.get('Risk', 'atr_stoploss_multiplier', fallback='2.0')),
        atr_takeprofit_multiplier=float(config.get('Risk', 'atr_takeprofit_multiplier', fallback='2.5')),
        trailing_stop_pct=float(config.get('Risk', 'trailing_stop_pct', fallback='0.06')),
        trailing_takeprofit_trigger_pct=float(config.get('Risk', 'trailing_takeprofit_trigger_pct', fallback='0.05')),
        trailing_takeprofit_pct=float(config.get('Risk', 'trailing_takeprofit_pct', fallback='0.02')),
        
        # 信号过滤
        min_volume_ratio=float(config.get('Strategy', 'min_volume_ratio', fallback='1.2')),
        max_atr_pct=float(config.get('Strategy', 'max_atr_pct', fallback='0.05')),
        trend_confirmation_period=int(config.get('Strategy', 'trend_confirmation_period', fallback='3')),
        
        # ========== 新增：6个优化点参数 ==========
        # 1. 信号强度阈值
        signal_strength_threshold=float(config.get('Optimization', 'signal_strength_threshold', fallback='20.0')),
        
        # 2. 信号强度权重（JSON字符串）
        signal_strength_weights_json=signal_strength_weights_json,
        
        # 3. 动态仓位分配
        position_size_by_strength=config.getboolean('Optimization', 'position_size_by_strength', fallback=True),
        strength_to_position_power=float(config.get('Optimization', 'strength_to_position_power', fallback='1.5')),
        
        # 4. 多时间框架确认
        multi_timeframe_confirmation=config.getboolean('Optimization', 'multi_timeframe_confirmation', fallback=True),
        higher_timeframe=config.get('Optimization', 'higher_timeframe', fallback='1h'),
        higher_timeframe_weight=float(config.get('Optimization', 'higher_timeframe_weight', fallback='0.3')),
        
        # 5. 止损止盈优化
        stop_loss_volatility_adjust=config.getboolean('Optimization', 'stop_loss_volatility_adjust', fallback=True),
        stop_loss_trend_adjust=config.getboolean('Optimization', 'stop_loss_trend_adjust', fallback=True),
        volatility_stop_multiplier=float(config.get('Optimization', 'volatility_stop_multiplier', fallback='2.0')),
        trend_stop_multiplier=float(config.get('Optimization', 'trend_stop_multiplier', fallback='1.5')),
        
        # 6. 机器学习信号评分
        ml_signal_scoring=config.getboolean('Optimization', 'ml_signal_scoring', fallback=False),
        ml_model_path=config.get('Optimization', 'ml_model_path', fallback=''),
        
        # 系统设置
        check_interval=int(config.get('System', 'check_interval', fallback='60')),
        enable_trading=config.getboolean('System', 'enable_trading', fallback=True),
        testnet=config.getboolean('System', 'testnet', fallback=True),
        enable_logging=config.getboolean('System', 'enable_logging', fallback=True),
        cache_indicators=config.getboolean('System', 'cache_indicators', fallback=True),
        use_simple_orders=config.getboolean('System', 'use_simple_orders', fallback=True),
    )


def setup_logging(enable_logging: bool = True):
    """设置日志"""
    if not enable_logging:
        logging.basicConfig(level=logging.WARNING)
        return
    
    # 创建日志目录
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 日志文件名
    log_file = os.path.join(log_dir, f'doomsday_fixed_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def main():
    """主函数"""
    print("=" * 70)
    print("OKX末日战车策略 - 优化版v2（集成6个优化点）")
    print("基于修复版，集成信号强度、动态仓位、多时间框架、止损优化")
    print("⚠️  极端高风险警告：可能几天内亏损50-100%本金")
    print("=" * 70)
    
    # 加载配置
    try:
        config = load_config()
    except Exception as e:
        print(f"❌ 加载配置失败: {e}")
        return
    
    # 设置日志
    setup_logging(config.enable_logging)
    logger = logging.getLogger(__name__)
    
    # 打印配置摘要
    logger.info("📋 配置摘要:")
    logger.info(f"   交易对: {config.symbol}")
    logger.info(f"   杠杆: {config.leverage}x")
    logger.info(f"   保证金模式: {config.margin_mode}")
    logger.info(f"   交易模式: {config.td_mode}")
    logger.info(f"   动态仓位: {config.base_position_size_pct*100:.1f}%-{config.max_position_size_pct*100:.1f}%")
    logger.info(f"   做空侧重: {config.short_bias*100:.1f}%")
    logger.info(f"   动量阈值: 做多{config.momentum_threshold_long*100:.1f}%, 做空{config.momentum_threshold_short*100:.1f}%")
    logger.info(f"   止损: {config.base_stoploss_pct*100:.1f}%, 止盈: {config.base_takeprofit_pct*100:.1f}%")
    logger.info(f"   动态止损: {config.atr_stoploss_multiplier}×ATR")
    logger.info(f"   动态止盈: {config.atr_takeprofit_multiplier}×ATR")
    logger.info(f"   启用交易: {config.enable_trading}")
    logger.info(f"   测试网: {config.testnet}")
    logger.info(f"   使用简单订单: {config.use_simple_orders}")
    
    # 打印优化配置摘要
    logger.info("📊 优化配置（v2）:")
    logger.info(f"   信号强度阈值: {config.signal_strength_threshold}（原15）")
    logger.info(f"   动态仓位分配: {config.position_size_by_strength}，强度指数: {config.strength_to_position_power}")
    logger.info(f"   多时间框架确认: {config.multi_timeframe_confirmation}，更高时间框架: {config.higher_timeframe}")
    logger.info(f"   止损波动率调整: {config.stop_loss_volatility_adjust}，乘数: {config.volatility_stop_multiplier}")
    logger.info(f"   止损趋势调整: {config.stop_loss_trend_adjust}，乘数: {config.trend_stop_multiplier}")
    logger.info(f"   机器学习评分: {config.ml_signal_scoring}（预留）")
    
    print(f"\n🚀 开始运行... 日志文件: logs/doomsday_fixed_*.log")
    print("按 Ctrl+C 停止程序\n")
    
    # 运行交易系统
    system = FixedTradingSystem(config)
    system.run()


if __name__ == "__main__":
    main()