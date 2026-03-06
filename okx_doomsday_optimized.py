#!/usr/bin/env python3
"""
OKX末日战车策略 - 优化版
基于Bybit末日战车策略优化，适配OKX交易所

主要优化：
1. 增强信号过滤（减少假信号，提高胜率）
2. 动态仓位管理（基于ATR调整仓位）
3. 改进风险控制（动态止损止盈）
4. OKX交易所完全适配
5. 性能优化（缓存指标计算）

⚠️ 风险警告：
- 极端激进策略，目标月利润50%+
- 可能几天内亏损50-100%本金
- 仅适用于愿意承担极高风险的小资金
- 需要OKX合约交易权限和10倍杠杆
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
import warnings
warnings.filterwarnings('ignore')


# ==================== 配置类 ====================
@dataclass
class Config:
    """交易配置 - 优化版"""
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
    margin_mode: str = "isolated"  # 逐仓模式
    
    # 动态仓位管理
    base_position_size_pct: float = 0.15  # 基础仓位15%
    max_position_size_pct: float = 0.25   # 最大仓位25%
    min_position_size_pct: float = 0.05   # 最小仓位5%
    atr_position_adjust: bool = True      # 根据ATR调整仓位
    
    # 交易限制
    max_daily_trades: int = 10           # 每日最大交易次数
    max_daily_loss_pct: float = 0.20     # 每日最大亏损20%
    max_total_loss_pct: float = 0.40     # 总最大亏损40%
    cooling_period_minutes: int = 5      # 连续亏损后冷却时间
    
    # 策略参数（优化）
    timeframe: str = "5m"                # 5分钟K线
    momentum_period: int = 5
    momentum_threshold_long: float = 0.008   # 做多动量阈值
    momentum_threshold_short: float = -0.008  # 做空动量阈值
    rsi_period: int = 7
    rsi_overbought: int = 70
    rsi_oversold: int = 30
    short_bias: float = 0.75             # 75%做空侧重
    
    # 动态止损止盈（优化）
    base_stoploss_pct: float = 0.25      # 基础止损25%
    base_takeprofit_pct: float = 0.30    # 基础止盈30%
    atr_stoploss_multiplier: float = 2.5  # ATR止损倍数
    atr_takeprofit_multiplier: float = 3.0  # ATR止盈倍数
    trailing_stop_pct: float = 0.08      # 移动止损8%
    
    # 信号过滤（新增）
    min_volume_ratio: float = 1.5        # 最小成交量比率
    max_atr_pct: float = 0.04            # 最大ATR百分比（过滤高波动）
    trend_confirmation_period: int = 3   # 趋势确认周期
    
    # 系统设置
    check_interval: int = 60             # 检查间隔(秒)
    enable_trading: bool = True          # 启用交易
    testnet: bool = True                 # 使用测试网
    enable_logging: bool = True          # 启用详细日志
    cache_indicators: bool = True        # 缓存技术指标


# ==================== 信号生成器（优化版） ====================
class OptimizedSignalGenerator:
    """优化信号生成器 - 减少假信号，提高胜率"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.cache = {}  # 指标缓存
        
    def _get_cache_key(self, df: pd.DataFrame, indicator_name: str) -> str:
        """生成缓存键"""
        # 使用最后50根K线的哈希值作为缓存键
        data_hash = hashlib.md5(pd.util.hash_pandas_object(df.tail(50)).values).hexdigest()
        return f"{indicator_name}_{data_hash}"
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算交易信号（优化版）"""
        if len(df) < 100:
            self.logger.warning(f"数据不足，只有{len(df)}根K线，需要至少100根")
            df['signal'] = 'hold'
            df['signal_strength'] = 0
            df['position_size'] = 0
            return df
        
        try:
            # ========== 技术指标计算（带缓存） ==========
            cache_key = self._get_cache_key(df, 'indicators')
            if self.config.cache_indicators and cache_key in self.cache:
                cached_result = self.cache[cache_key]
                df = df.copy()
                for col in cached_result.columns:
                    if col in df.columns:
                        df[col] = cached_result[col]
            else:
                df = self._calculate_indicators(df)
                if self.config.cache_indicators:
                    self.cache[cache_key] = df[list(set(df.columns) - set(['open', 'high', 'low', 'close', 'volume']))].copy()
            
            # ========== 信号生成（优化逻辑） ==========
            df = self._generate_signals(df)
            
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
            df['signal_strength'] = 0
            df['position_size'] = 0
        
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
        
        # 均线系统（多周期）
        df['ma_fast'] = df['close'].rolling(window=7).mean()
        df['ma_medium'] = df['close'].rolling(window=21).mean()
        df['ma_slow'] = df['close'].rolling(window=50).mean()
        df['ma_trend'] = df['close'].rolling(window=100).mean()
        
        # 趋势强度
        df['trend_strength'] = abs(df['ma_fast'] - df['ma_slow']) / df['atr']
        df['trend_direction'] = np.sign(df['ma_fast'] - df['ma_slow'])
        
        # MACD（新增）
        df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(df['close'])
        df['macd_trend'] = df['macd'] > df['macd_signal']
        
        return df
    
    def _generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号（优化逻辑）"""
        # 初始化信号列
        df['long_signal_raw'] = False
        df['short_signal_raw'] = False
        
        # ========== 做多信号（优化条件） ==========
        # 1. 强势突破做多（需成交量确认）
        long_breakout = (
            (df['close'] > df['high_15'].shift(1)) &
            (df['volume_ratio'] > self.config.min_volume_ratio) &
            (df['momentum'] > self.config.momentum_threshold_long) &
            (df['rsi'] > 40) & (df['rsi'] < 70) &
            (df['trend_direction'] > 0) &  # 趋势向上
            (df['macd_trend'])  # MACD金叉
        )
        
        # 2. 超跌反弹做多（RSI底背离）
        rsi_bullish_divergence = (
            (df['rsi'] < self.config.rsi_oversold) &
            (df['rsi'] > df['rsi'].shift(1)) &
            (df['close'] < df['close'].shift(1)) &  # 价格新低，RSI不新低
            (df['momentum'] > 0.002) &
            (df['bb_position'] < 0.2) &
            df['volume_spike']
        )
        
        # 3. 趋势跟随做多（多均线确认）
        long_trend = (
            (df['ma_fast'] > df['ma_medium']) &
            (df['ma_medium'] > df['ma_slow']) &
            (df['momentum'] > 0.005) &
            (df['close'] > df['ma_fast']) &
            (df['trend_strength'] > 1.0)  # 趋势强度足够
        )
        
        df['long_signal_raw'] = long_breakout | rsi_bullish_divergence | long_trend
        
        # ========== 做空信号（优化条件） ==========
        # 1. 弱势突破做空
        short_breakout = (
            (df['close'] < df['low_15'].shift(1)) &
            (df['volume_ratio'] > self.config.min_volume_ratio) &
            (df['momentum'] < self.config.momentum_threshold_short) &
            (df['rsi'] > 30) & (df['rsi'] < 80) &
            (df['trend_direction'] < 0) &  # 趋势向下
            (~df['macd_trend'])  # MACD死叉
        )
        
        # 2. 超买回调做空（RSI顶背离）
        rsi_bearish_divergence = (
            (df['rsi'] > self.config.rsi_overbought) &
            (df['rsi'] < df['rsi'].shift(1)) &
            (df['close'] > df['close'].shift(1)) &  # 价格新高，RSI不新高
            (df['momentum'] < -0.002) &
            (df['bb_position'] > 0.8) &
            df['volume_spike']
        )
        
        # 3. 趋势跟随做空
        short_trend = (
            (df['ma_fast'] < df['ma_medium']) &
            (df['ma_medium'] < df['ma_slow']) &
            (df['momentum'] < -0.005) &
            (df['close'] < df['ma_fast']) &
            (df['trend_strength'] > 1.0)
        )
        
        df['short_signal_raw'] = short_breakout | rsi_bearish_divergence | short_trend
        
        return df
    
    def _filter_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """过滤信号（减少假信号）"""
        # 初始化最终信号列
        df['signal'] = 'hold'
        df['signal_strength'] = 0.0  # 使用浮点数类型
        
        # 过滤条件
        valid_condition = (
            (df['atr_pct'] < self.config.max_atr_pct) &  # 过滤高波动
            (df['volume'] > 0) &  # 有成交量
            (abs(df['momentum']) < 0.05)  # 过滤极端波动
        )
        
        # 做多信号过滤
        long_condition = df['long_signal_raw'] & valid_condition
        df.loc[long_condition, 'signal'] = 'long'
        
        # 做空信号过滤（应用做空侧重）
        short_condition = df['short_signal_raw'] & valid_condition
        
        # 随机过滤部分做空信号（如果做空侧重<1.0）
        if self.config.short_bias < 1.0:
            np.random.seed(int(time.time()) % 1000)
            random_filter = np.random.random(len(df)) < self.config.short_bias
            short_condition = short_condition & random_filter
        
        df.loc[short_condition, 'signal'] = 'short'
        
        # 计算信号强度
        df.loc[df['signal'] == 'long', 'signal_strength'] = self._calculate_signal_strength(df, 'long')
        df.loc[df['signal'] == 'short', 'signal_strength'] = self._calculate_signal_strength(df, 'short')
        
        # 避免频繁交易：同一方向信号需间隔至少3根K线
        df = self._avoid_overtrading(df)
        
        return df
    
    def _calculate_signal_strength(self, df: pd.DataFrame, signal_type: str) -> float:
        """计算信号强度（0-10）"""
        if signal_type == 'long':
            strength = (
                df['momentum'].abs() * 15 +
                df['volume_ratio'] * 1.0 +
                (df['rsi'] - 30) / 40 * 3 +
                df['trend_strength'] * 2 +
                (df['bb_position'] * 5)  # 布林带位置
            )
        else:  # short
            strength = (
                df['momentum'].abs() * 15 +
                df['volume_ratio'] * 1.0 +
                (70 - df['rsi']) / 40 * 3 +
                df['trend_strength'] * 2 +
                ((1 - df['bb_position']) * 5)
            )
        
        # 标准化到0-10范围
        strength = strength.clip(0, 30) / 3.0
        return strength.round(2)
    
    def _calculate_position_size(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算仓位大小（基于ATR动态调整）"""
        df['position_size'] = self.config.base_position_size_pct
        
        if self.config.atr_position_adjust:
            # 根据ATR调整仓位：波动率低时加仓，高时减仓
            atr_adjustment = (df['atr_ma'] / df['atr_pct']).clip(0.5, 2.0)
            df['position_size'] = df['position_size'] * atr_adjustment
            
            # 根据信号强度调整
            strength_adjustment = 0.5 + (df['signal_strength'] / 20)  # 0.5-1.5倍
            df['position_size'] = df['position_size'] * strength_adjustment
            
            # 限制仓位范围
            df['position_size'] = df['position_size'].clip(
                self.config.min_position_size_pct,
                self.config.max_position_size_pct
            )
        
        return df
    
    def _avoid_overtrading(self, df: pd.DataFrame) -> pd.DataFrame:
        """避免过度交易：同一方向信号需间隔"""
        for i in range(1, len(df)):
            if df.iloc[i]['signal'] != 'hold' and df.iloc[i]['signal'] == df.iloc[i-1]['signal']:
                # 同一方向连续信号，只保留第一个
                df.iloc[i, df.columns.get_loc('signal')] = 'hold'
                df.iloc[i, df.columns.get_loc('signal_strength')] = 0
        
        return df
    
    def get_current_signal(self, df: pd.DataFrame) -> Tuple[str, float, float]:
        """获取最新信号和推荐仓位"""
        if len(df) == 0:
            return 'hold', 0, 0
        
        latest = df.iloc[-1]
        return latest['signal'], latest['signal_strength'], latest['position_size']


# ==================== OKX交易器（优化版） ====================
class OKXDoomsdayTraderOptimized:
    """OKX末日战车交易执行器 - 优化版"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 初始化交易所
        self.exchange = self._init_exchange()
        
        # 状态变量
        self.position = None
        self.position_entry_price = 0.0
        self.position_type = None  # 'long' or 'short'
        self.today_trades = 0
        self.today_pnl = 0.0
        self.total_pnl = 0.0
        self.last_trade_time = None
        self.consecutive_losses = 0
        self.is_running = True
        
        # 信号生成器
        self.signal_generator = OptimizedSignalGenerator(config)
        
        # 交易统计
        self.trade_stats = {
            'total_trades': 0,
            'long_trades': 0,
            'short_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_profit': 0.0,
            'total_loss': 0.0,
        }
        
        # 缓存K线数据
        self.ohlcv_cache = None
        self.last_ohlcv_update = None
        
        self.logger.info("OKX末日战车优化版交易系统初始化完成")
        self.logger.info(f"交易对: {config.symbol}, 杠杆: {config.leverage}x")
        self.logger.info(f"动态仓位: {config.base_position_size_pct*100}%-{config.max_position_size_pct*100}%")
        self.logger.info(f"做空侧重: {config.short_bias*100}%, 测试网: {config.testnet}")
    
    def _init_exchange(self):
        """初始化OKX交易所"""
        exchange_config = {
            'apiKey': self.config.api_key,
            'secret': self.config.api_secret,
            'password': self.config.api_password,  # OKX需要passphrase
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # 永续合约
                'sandbox': self.config.testnet,  # 测试网 - 使用sandbox而不是test
            }
        }
        
        exchange = ccxt.okx(exchange_config)
        
        # 测试连接
        try:
            exchange.fetch_balance()
            self.logger.info("✅ OKX连接成功")
        except Exception as e:
            self.logger.error(f"❌ OKX连接失败: {e}")
            raise
        
        return exchange
    
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
    
    def fetch_ohlcv(self, limit: int = 100) -> pd.DataFrame:
        """获取K线数据（带缓存）"""
        cache_key = f"{self.config.symbol}_{self.config.timeframe}_{limit}"
        
        # 检查缓存（5分钟内有效）
        if (self.ohlcv_cache is not None and 
            self.last_ohlcv_update is not None and
            (time.time() - self.last_ohlcv_update) < 300):
            return self.ohlcv_cache
        
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
            
            # 更新缓存
            self.ohlcv_cache = df
            self.last_ohlcv_update = time.time()
            
            return df
            
        except Exception as e:
            self.logger.error(f"获取K线失败: {e}")
            return pd.DataFrame()
    
    def fetch_position(self):
        """获取当前持仓"""
        try:
            positions = self.exchange.fetch_positions([self.config.symbol])
            for pos in positions:
                if pos['symbol'] == self.config.symbol:
                    contracts = pos.get('contracts', 0)
                    if abs(float(contracts)) > 0.001:
                        self.position = pos
                        self.position_type = 'long' if float(contracts) > 0 else 'short'
                        self.position_entry_price = pos.get('entryPrice', 0)
                        return
            
            self.position = None
            self.position_type = None
            self.position_entry_price = 0.0
            
        except Exception as e:
            self.logger.error(f"获取持仓失败: {e}")
            self.position = None
    
    def calculate_position_size(self, current_price: float) -> float:
        """计算仓位大小（优化版）"""
        try:
            # 获取余额
            balance = self.exchange.fetch_balance()
            free_usdt = balance['USDT']['free']
            
            # 基础仓位计算
            position_value = free_usdt * self.config.base_position_size_pct
            
            # 根据当前信号强度调整（如果有信号）
            if self.ohlcv_cache is not None and len(self.ohlcv_cache) > 0:
                df = self.signal_generator.calculate_signals(self.ohlcv_cache)
                _, signal_strength, position_size_pct = self.signal_generator.get_current_signal(df)
                if position_size_pct > 0:
                    position_value = free_usdt * position_size_pct
            
            # 计算合约数量
            position_size = position_value * self.config.leverage / current_price
            
            # OKX最小交易单位
            min_size = 0.01  # ETH最小交易单位
            position_size = max(position_size, min_size)
            
            # 取整
            position_size = round(position_size, 2)
            
            return position_size
            
        except Exception as e:
            self.logger.error(f"计算仓位失败: {e}")
            return 0.0
    
    def calculate_dynamic_stop_loss_take_profit(self, current_price: float, signal_type: str):
        """计算动态止损止盈"""
        # 获取ATR
        atr = 0
        if self.ohlcv_cache is not None and len(self.ohlcv_cache) > 0:
            atr = self.ohlcv_cache['atr'].iloc[-1] if 'atr' in self.ohlcv_cache.columns else current_price * 0.02
        
        if signal_type == 'long':
            # 做多：止损在下方，止盈在上方
            stop_loss_price = current_price - (atr * self.config.atr_stoploss_multiplier)
            take_profit_price = current_price + (atr * self.config.atr_takeprofit_multiplier)
        else:
            # 做空：止损在上方，止盈在下方
            stop_loss_price = current_price + (atr * self.config.atr_stoploss_multiplier)
            take_profit_price = current_price - (atr * self.config.atr_takeprofit_multiplier)
        
        # 确保价格合理
        stop_loss_price = max(stop_loss_price, 0.1)
        take_profit_price = max(take_profit_price, 0.1)
        
        return stop_loss_price, take_profit_price
    
    def check_stop_loss_take_profit(self, current_price: float) -> Optional[str]:
        """检查止损止盈"""
        if self.position_type is None or self.position_entry_price == 0:
            return None
        
        if self.position_type == 'long':
            profit_pct = (current_price - self.position_entry_price) / self.position_entry_price
        else:
            profit_pct = (self.position_entry_price - current_price) / self.position_entry_price
        
        # 检查止损
        if profit_pct <= -self.config.base_stoploss_pct:
            return 'stop_loss'
        
        # 检查止盈
        if profit_pct >= self.config.base_takeprofit_pct:
            return 'take_profit'
        
        return None
    
    def place_order(self, order_type: str, position_size: float, 
                    current_price: float, signal_type: str) -> bool:
        """下单"""
        if not self.config.enable_trading:
            self.logger.info(f"模拟交易: {order_type} {position_size} {self.config.symbol} @ {current_price}")
            return True
        
        try:
            # 计算动态止损止盈
            stop_loss_price, take_profit_price = self.calculate_dynamic_stop_loss_take_profit(
                current_price, signal_type
            )
            
            # OKX下单参数
            order_params = {
                'symbol': self.config.symbol,
                'type': 'market',
                'side': order_type,
                'amount': position_size,
                'params': {
                    'stopLoss': {
                        'triggerPrice': stop_loss_price,
                        'price': stop_loss_price * 0.995 if order_type == 'buy' else stop_loss_price * 1.005,
                        'type': 'market'
                    },
                    'takeProfit': {
                        'triggerPrice': take_profit_price,
                        'price': take_profit_price * 0.995 if order_type == 'buy' else take_profit_price * 1.005,
                        'type': 'market'
                    }
                }
            }
            
            # 下单
            order = self.exchange.create_order(**order_params)
            self.logger.info(f"下单成功: {order_type} {position_size} {self.config.symbol}")
            self.logger.info(f"止损: {stop_loss_price:.2f}, 止盈: {take_profit_price:.2f}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"下单失败: {e}")
            return False
    
    def close_position(self, reason: str = 'signal') -> bool:
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
            
            # 平仓
            order = self.exchange.create_order(
                symbol=self.config.symbol,
                type='market',
                side=side,
                amount=position_size
            )
            
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
            else:
                self.trade_stats['losing_trades'] += 1
                self.trade_stats['total_loss'] += abs(pnl_pct)
                self.consecutive_losses += 1
            
            self.total_pnl += pnl_pct
            self.today_pnl += pnl_pct
            
            self.logger.info(f"平仓完成: {self.position_type}, 盈亏: {pnl_pct:.2f}%, 原因: {reason}")
            self.logger.info(f"累计盈亏: {self.total_pnl:.2f}%, 今日盈亏: {self.today_pnl:.2f}%")
            
            # 重置持仓状态
            self.position = None
            self.position_type = None
            self.position_entry_price = 0.0
            
            return True
            
        except Exception as e:
            self.logger.error(f"平仓失败: {e}")
            return False
    
    def check_daily_limits(self) -> bool:
        """检查每日限制"""
        # 检查每日交易次数
        if self.today_trades >= self.config.max_daily_trades:
            self.logger.warning(f"达到每日最大交易次数限制: {self.today_trades}/{self.config.max_daily_trades}")
            return False
        
        # 检查每日亏损
        if self.today_pnl <= -self.config.max_daily_loss_pct * 100:
            self.logger.error(f"达到每日最大亏损限制: {self.today_pnl:.2f}%")
            self.is_running = False
            return False
        
        # 检查总亏损
        if self.total_pnl <= -self.config.max_total_loss_pct * 100:
            self.logger.error(f"达到总最大亏损限制: {self.total_pnl:.2f}%")
            self.is_running = False
            return False
        
        # 检查冷却时间
        if self.consecutive_losses >= 3:
            self.logger.warning(f"连续亏损{self.consecutive_losses}次，进入冷却期")
            time.sleep(self.config.cooling_period_minutes * 60)
            self.consecutive_losses = 0
        
        return True
    
    def reset_daily_stats(self):
        """重置每日统计"""
        now = datetime.now()
        if self.last_trade_time is None or now.date() != self.last_trade_time.date():
            self.today_trades = 0
            self.today_pnl = 0.0
            self.last_trade_time = now
            self.logger.info("新的一天，重置每日统计")
    
    def print_stats(self):
        """打印统计信息"""
        total_trades = self.trade_stats['total_trades']
        if total_trades == 0:
            return
        
        win_rate = (self.trade_stats['winning_trades'] / total_trades * 100) if total_trades > 0 else 0
        avg_profit = (self.trade_stats['total_profit'] / self.trade_stats['winning_trades']) if self.trade_stats['winning_trades'] > 0 else 0
        avg_loss = (self.trade_stats['total_loss'] / self.trade_stats['losing_trades']) if self.trade_stats['losing_trades'] > 0 else 0
        profit_factor = avg_profit / avg_loss if avg_loss > 0 else 0
        
        self.logger.info("=" * 60)
        self.logger.info("交易统计:")
        self.logger.info(f"  总交易次数: {total_trades}")
        self.logger.info(f"  做多交易: {self.trade_stats['long_trades']}")
        self.logger.info(f"  做空交易: {self.trade_stats['short_trades']}")
        self.logger.info(f"  胜率: {win_rate:.1f}%")
        self.logger.info(f"  平均盈利: {avg_profit:.2f}%")
        self.logger.info(f"  平均亏损: {avg_loss:.2f}%")
        self.logger.info(f"  盈亏比: {profit_factor:.2f}")
        self.logger.info(f"  累计盈亏: {self.total_pnl:.2f}%")
        self.logger.info(f"  今日盈亏: {self.today_pnl:.2f}%")
        self.logger.info("=" * 60)
    
    def run(self):
        """运行交易系统"""
        self.logger.info("开始运行交易系统...")
        
        # 设置杠杆
        self.set_leverage()
        
        # 主循环
        while self.is_running:
            try:
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
                
                # 获取当前持仓
                self.fetch_position()
                
                # 计算信号
                df = self.signal_generator.calculate_signals(df)
                signal, signal_strength, position_size_pct = self.signal_generator.get_current_signal(df)
                
                # 获取当前价格
                current_price = df['close'].iloc[-1]
                
                # 检查止损止盈
                stop_take_reason = self.check_stop_loss_take_profit(current_price)
                if stop_take_reason is not None:
                    self.logger.info(f"触发{stop_take_reason}，执行平仓")
                    self.close_position(stop_take_reason)
                    time.sleep(self.config.check_interval)
                    continue
                
                # 处理交易信号
                if signal != 'hold' and signal_strength > 0:
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


# ==================== 辅助函数 ====================
def load_config(config_file: str = 'config.ini') -> Config:
    """加载配置文件"""
    config = configparser.ConfigParser()
    
    if not os.path.exists(config_file):
        print(f"配置文件不存在: {config_file}")
        print("请创建config.ini文件，参考config.ini.example")
        sys.exit(1)
    
    config.read(config_file)
    
    return Config(
        # OKX API
        api_key=config.get('OKX', 'api_key', fallback=''),
        api_secret=config.get('OKX', 'api_secret', fallback=''),
        api_password=config.get('OKX', 'api_password', fallback=''),
        
        # 交易对
        symbol=config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP'),
        base_currency=config.get('Trading', 'base_currency', fallback='ETH'),
        quote_currency=config.get('Trading', 'quote_currency', fallback='USDT'),
        
        # 杠杆设置
        leverage=int(config.get('Trading', 'leverage', fallback='10')),
        margin_mode=config.get('Trading', 'margin_mode', fallback='isolated'),
        
        # 动态仓位管理
        base_position_size_pct=float(config.get('Trading', 'base_position_size_pct', fallback='0.15')),
        max_position_size_pct=float(config.get('Trading', 'max_position_size_pct', fallback='0.25')),
        min_position_size_pct=float(config.get('Trading', 'min_position_size_pct', fallback='0.05')),
        atr_position_adjust=config.getboolean('Trading', 'atr_position_adjust', fallback=True),
        
        # 交易限制
        max_daily_trades=int(config.get('Trading', 'max_daily_trades', fallback='10')),
        max_daily_loss_pct=float(config.get('Trading', 'max_daily_loss_pct', fallback='0.20')),
        max_total_loss_pct=float(config.get('Trading', 'max_total_loss_pct', fallback='0.40')),
        cooling_period_minutes=int(config.get('Trading', 'cooling_period_minutes', fallback='5')),
        
        # 策略参数
        timeframe=config.get('Strategy', 'timeframe', fallback='5m'),
        momentum_period=int(config.get('Strategy', 'momentum_period', fallback='5')),
        momentum_threshold_long=float(config.get('Strategy', 'momentum_threshold_long', fallback='0.008')),
        momentum_threshold_short=float(config.get('Strategy', 'momentum_threshold_short', fallback='-0.008')),
        rsi_period=int(config.get('Strategy', 'rsi_period', fallback='7')),
        rsi_overbought=int(config.get('Strategy', 'rsi_overbought', fallback='70')),
        rsi_oversold=int(config.get('Strategy', 'rsi_oversold', fallback='30')),
        short_bias=float(config.get('Strategy', 'short_bias', fallback='0.75')),
        
        # 动态止损止盈
        base_stoploss_pct=float(config.get('Risk', 'base_stoploss_pct', fallback='0.25')),
        base_takeprofit_pct=float(config.get('Risk', 'base_takeprofit_pct', fallback='0.30')),
        atr_stoploss_multiplier=float(config.get('Risk', 'atr_stoploss_multiplier', fallback='2.5')),
        atr_takeprofit_multiplier=float(config.get('Risk', 'atr_takeprofit_multiplier', fallback='3.0')),
        trailing_stop_pct=float(config.get('Risk', 'trailing_stop_pct', fallback='0.08')),
        
        # 信号过滤
        min_volume_ratio=float(config.get('Strategy', 'min_volume_ratio', fallback='1.5')),
        max_atr_pct=float(config.get('Strategy', 'max_atr_pct', fallback='0.04')),
        trend_confirmation_period=int(config.get('Strategy', 'trend_confirmation_period', fallback='3')),
        
        # 系统设置
        check_interval=int(config.get('System', 'check_interval', fallback='60')),
        enable_trading=config.getboolean('System', 'enable_trading', fallback=True),
        testnet=config.getboolean('System', 'testnet', fallback=True),
        enable_logging=config.getboolean('System', 'enable_logging', fallback=True),
        cache_indicators=config.getboolean('System', 'cache_indicators', fallback=True),
    )


def setup_logging(enable_logging: bool = True):
    """设置日志"""
    if not enable_logging:
        logging.basicConfig(level=logging.WARNING)
        return
    
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f'doomsday_optimized_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


# ==================== 主函数 ====================
def main():
    """主函数"""
    print("=" * 70)
    print("OKX末日战车策略 - 优化版")
    print("基于Bybit末日战车策略优化，适配OKX交易所")
    print("⚠️  极端高风险警告：可能几天内亏损50-100%本金")
    print("=" * 70)
    
    # 设置日志
    setup_logging(enable_logging=True)
    logger = logging.getLogger(__name__)
    
    # 加载配置
    config = load_config()
    
    # 验证API密钥
    if config.api_key == 'YOUR_API_KEY_HERE' or not config.api_key:
        logger.error("请先在config.ini中配置OKX API密钥")
        sys.exit(1)
    
    # 创建交易系统
    try:
        trader = OKXDoomsdayTraderOptimized(config)
        
        # 显示配置确认
        print("\n🔧 配置确认:")
        print(f"  交易对: {config.symbol}")
        print(f"  杠杆: {config.leverage}x")
        print(f"  仓位范围: {config.base_position_size_pct*100:.1f}%-{config.max_position_size_pct*100:.1f}%")
        print(f"  做空侧重: {config.short_bias*100:.0f}%")
        print(f"  动态止损: {config.atr_stoploss_multiplier:.1f}×ATR")
        print(f"  动态止盈: {config.atr_takeprofit_multiplier:.1f}×ATR")
        print(f"  启用交易: {config.enable_trading}")
        print(f"  测试网: {config.testnet}")
        
        if config.enable_trading and not config.testnet:
            print("\n⚠️  ⚠️  ⚠️  警告：实盘交易模式已启用！")
            print("   将会进行真实交易，可能造成资金损失！")
            confirm = input("\n确认开始实盘交易？(输入 YES 确认): ")
            if confirm != 'YES':
                print("已取消")
                sys.exit(0)
        
        # 运行交易系统
        print(f"\n🚀 开始运行... 日志文件: logs/doomsday_optimized_*.log")
        print("按 Ctrl+C 停止程序")
        trader.run()
        
    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"程序异常: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()