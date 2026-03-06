#!/usr/bin/env python3
"""
诊断策略为何不开仓
"""

import os
import sys
import json
import logging
import pandas as pd
import numpy as np
from typing import Optional, Tuple
import configparser
from dataclasses import dataclass
import ccxt
import time

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置类
@dataclass
class Config:
    api_key: str
    api_secret: str
    api_password: str
    symbol: str = 'ETH-USDT-SWAP'
    leverage: int = 10
    margin_mode: str = 'cross'
    base_position_size_pct: float = 0.3
    max_position_size_pct: float = 0.3
    min_position_size_pct: float = 0.05
    atr_position_adjust: bool = True
    max_daily_trades: int = 30
    max_daily_loss_pct: float = 0.25
    max_total_loss_pct: float = 0.40
    cooling_period_minutes: int = 2
    timeframe: str = '5m'
    momentum_period: int = 5
    momentum_threshold_long: float = 0.005
    momentum_threshold_short: float = -0.005
    rsi_period: int = 7
    rsi_overbought: int = 75
    rsi_oversold: int = 25
    short_bias: float = 0.50
    min_volume_ratio: float = 1.2
    max_atr_pct: float = 0.05
    trend_confirmation_period: int = 1
    base_stoploss_pct: float = 0.05
    base_takeprofit_pct: float = 0.09
    atr_stoploss_multiplier: float = 1.5
    atr_takeprofit_multiplier: float = 2.0
    trailing_stop_pct: float = 0.03
    signal_strength_threshold: float = 15
    signal_strength_weights_json: str = '{"momentum": 0.15, "volume": 0.10, "rsi": 0.15, "trend": 0.20, "bb": 0.10, "volatility": 0.10, "multi_timeframe": 0.10, "sentiment": 0.10}'
    position_size_by_strength: bool = True
    strength_to_position_power: float = 1.5
    multi_timeframe_confirmation: bool = True
    higher_timeframe: str = '1h'
    higher_timeframe_weight: float = 0.3
    stop_loss_volatility_adjust: bool = True
    stop_loss_trend_adjust: bool = True
    volatility_stop_multiplier: float = 2.0
    trend_stop_multiplier: float = 1.5
    ml_signal_scoring: bool = True
    ml_model_path: str = ''
    ml_data_collection: bool = True
    ml_data_dir: str = 'ml_data'
    ml_min_samples: int = 1000
    ml_retrain_days: int = 7
    check_interval: int = 60
    enable_trading: bool = True
    testnet: bool = True
    enable_logging: bool = True
    cache_indicators: bool = False
    vps_location: str = 'HongKong'
    td_mode: str = 'cross'
    use_simple_orders: bool = True

def load_config() -> Config:
    """加载配置文件"""
    config_file = 'config_optimized_v2.ini'
    if not os.path.exists(config_file):
        config_file = 'config.ini'
    
    logger.info(f"使用配置文件: {config_file}")
    config = configparser.ConfigParser()
    config.read(config_file)
    
    signal_strength_weights_json = config.get('Optimization', 'signal_strength_weights', 
        fallback='{"momentum": 0.15, "volume": 0.10, "rsi": 0.15, "trend": 0.20, "bb": 0.10, "volatility": 0.10, "multi_timeframe": 0.10, "sentiment": 0.10}')
    
    return Config(
        api_key=config.get('OKX', 'api_key', fallback=''),
        api_secret=config.get('OKX', 'api_secret', fallback=''),
        api_password=config.get('OKX', 'api_password', fallback=''),
        symbol=config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP'),
        leverage=int(config.get('Trading', 'leverage', fallback='10')),
        margin_mode=config.get('Trading', 'margin_mode', fallback='cross'),
        base_position_size_pct=float(config.get('Trading', 'base_position_size_pct', fallback='0.3')),
        max_position_size_pct=float(config.get('Trading', 'max_position_size_pct', fallback='0.3')),
        min_position_size_pct=float(config.get('Trading', 'min_position_size_pct', fallback='0.05')),
        atr_position_adjust=config.get('Trading', 'atr_position_adjust', fallback='true').lower() == 'true',
        max_daily_trades=int(config.get('Trading', 'max_daily_trades', fallback='30')),
        max_daily_loss_pct=float(config.get('Trading', 'max_daily_loss_pct', fallback='0.25')),
        max_total_loss_pct=float(config.get('Trading', 'max_total_loss_pct', fallback='0.40')),
        cooling_period_minutes=int(config.get('Trading', 'cooling_period_minutes', fallback='2')),
        timeframe=config.get('Strategy', 'timeframe', fallback='5m'),
        momentum_period=int(config.get('Strategy', 'momentum_period', fallback='5')),
        momentum_threshold_long=float(config.get('Strategy', 'momentum_threshold_long', fallback='0.005')),
        momentum_threshold_short=float(config.get('Strategy', 'momentum_threshold_short', fallback='-0.005')),
        rsi_period=int(config.get('Strategy', 'rsi_period', fallback='7')),
        rsi_overbought=int(config.get('Strategy', 'rsi_overbought', fallback='75')),
        rsi_oversold=int(config.get('Strategy', 'rsi_oversold', fallback='25')),
        short_bias=float(config.get('Strategy', 'short_bias', fallback='0.50')),
        min_volume_ratio=float(config.get('Strategy', 'min_volume_ratio', fallback='1.2')),
        max_atr_pct=float(config.get('Strategy', 'max_atr_pct', fallback='0.05')),
        trend_confirmation_period=int(config.get('Strategy', 'trend_confirmation_period', fallback='1')),
        base_stoploss_pct=float(config.get('Risk', 'base_stoploss_pct', fallback='0.05')),
        base_takeprofit_pct=float(config.get('Risk', 'base_takeprofit_pct', fallback='0.09')),
        atr_stoploss_multiplier=float(config.get('Risk', 'atr_stoploss_multiplier', fallback='1.5')),
        atr_takeprofit_multiplier=float(config.get('Risk', 'atr_takeprofit_multiplier', fallback='2.0')),
        trailing_stop_pct=float(config.get('Risk', 'trailing_stop_pct', fallback='0.03')),
        signal_strength_threshold=float(config.get('Optimization', 'signal_strength_threshold', fallback='15')),
        signal_strength_weights_json=signal_strength_weights_json,
        position_size_by_strength=config.get('Optimization', 'position_size_by_strength', fallback='true').lower() == 'true',
        strength_to_position_power=float(config.get('Optimization', 'strength_to_position_power', fallback='1.5')),
        multi_timeframe_confirmation=config.get('Optimization', 'multi_timeframe_confirmation', fallback='true').lower() == 'true',
        higher_timeframe=config.get('Optimization', 'higher_timeframe', fallback='1h'),
        higher_timeframe_weight=float(config.get('Optimization', 'higher_timeframe_weight', fallback='0.3')),
        stop_loss_volatility_adjust=config.get('Optimization', 'stop_loss_volatility_adjust', fallback='true').lower() == 'true',
        stop_loss_trend_adjust=config.get('Optimization', 'stop_loss_trend_adjust', fallback='true').lower() == 'true',
        volatility_stop_multiplier=float(config.get('Optimization', 'volatility_stop_multiplier', fallback='2.0')),
        trend_stop_multiplier=float(config.get('Optimization', 'trend_stop_multiplier', fallback='1.5')),
        ml_signal_scoring=config.get('Optimization', 'ml_signal_scoring', fallback='true').lower() == 'true',
        ml_model_path=config.get('Optimization', 'ml_model_path', fallback=''),
        ml_data_collection=config.get('Optimization', 'ml_data_collection', fallback='true').lower() == 'true',
        ml_data_dir=config.get('Optimization', 'ml_data_dir', fallback='ml_data'),
        ml_min_samples=int(config.get('Optimization', 'ml_min_samples', fallback='1000')),
        ml_retrain_days=int(config.get('Optimization', 'ml_retrain_days', fallback='7')),
        check_interval=int(config.get('System', 'check_interval', fallback='60')),
        enable_trading=config.get('System', 'enable_trading', fallback='true').lower() == 'true',
        testnet=config.get('System', 'testnet', fallback='true').lower() == 'true',
        enable_logging=config.get('System', 'enable_logging', fallback='true').lower() == 'true',
        cache_indicators=config.get('System', 'cache_indicators', fallback='false').lower() == 'true',
        vps_location=config.get('System', 'vps_location', fallback='HongKong'),
        td_mode=config.get('System', 'td_mode', fallback='cross'),
        use_simple_orders=config.get('System', 'use_simple_orders', fallback='true').lower() == 'true',
    )

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
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标（简化版）"""
        # 动量指标
        df['momentum'] = df['close'].pct_change(periods=self.config.momentum_period)
        df['momentum_3'] = df['close'].pct_change(periods=3)
        df['momentum_7'] = df['close'].pct_change(periods=7)
        df['momentum_acc'] = df['momentum'].diff()
        
        # 成交量分析
        df['volume_ma'] = df['volume'].rolling(window=10).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        df['volume_trend'] = df['volume'].rolling(window=5).mean().diff()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.config.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.config.rsi_period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 移动平均线
        df['ma_fast'] = df['close'].rolling(window=7).mean()
        df['ma_medium'] = df['close'].rolling(window=21).mean()
        df['ma_slow'] = df['close'].rolling(window=50).mean()
        
        # 趋势强度
        df['trend_strength'] = np.where(
            df['ma_fast'] > df['ma_medium'], 1,
            np.where(df['ma_fast'] < df['ma_medium'], -1, 0)
        )
        
        # 布林带
        df['bb_middle'] = df['close'].rolling(window=15).mean()
        bb_std = df['close'].rolling(window=15).std()
        df['bb_upper'] = df['bb_middle'] + 2 * bb_std
        df['bb_lower'] = df['bb_middle'] - 2 * bb_std
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # ATR波动率
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['atr'] = true_range.rolling(window=14).mean()
        df['atr_pct'] = df['atr'] / df['close']
        
        # 波动率区间
        df['volatility_regime'] = pd.cut(df['atr_pct'], 
                                         bins=[0, 0.01, 0.02, 0.03, 0.05, 1],
                                         labels=[0, 1, 2, 3, 4]).astype(int)
        
        return df
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算交易信号（简化版，仅用于诊断）"""
        try:
            # 计算指标
            df = self._calculate_indicators(df)
            
            # 初始化信号列
            df['signal'] = 'hold'
            
            # 做多条件组
            long_condition1 = (
                (df['momentum'] > self.config.momentum_threshold_long) &
                (df['volume_ratio'] > self.config.min_volume_ratio) &
                (df['rsi'] > self.config.rsi_oversold) &
                (df['rsi'] < self.config.rsi_overbought) &
                (df['trend_strength'] > 0) &
                (df['momentum_7'] > 0.01) &
                (df['close'] > df['ma_fast']) &
                (df['volume_trend'] > 0) &
                (df['volatility_regime'] < 3)
            )
            
            long_condition2 = (
                (df['momentum'] > self.config.momentum_threshold_long * 1.5) &
                (df['volume_ratio'] > self.config.min_volume_ratio * 1.2) &
                (df['rsi'] < 50) &
                (df['trend_strength'] > 0) &
                (df['momentum_acc'] > 0)
            )
            
            long_condition3 = (
                (df['bb_position'] < 0.2) &
                (df['momentum'] > 0) &
                (df['volume_ratio'] > 1.5) &
                (df['rsi'] < 40)
            )
            
            # 做空条件组
            short_condition1 = (
                (df['momentum'] < self.config.momentum_threshold_short) &
                (df['volume_ratio'] > self.config.min_volume_ratio) &
                (df['rsi'] > self.config.rsi_oversold) &
                (df['rsi'] < self.config.rsi_overbought) &
                (df['trend_strength'] < 0) &
                (df['momentum_7'] < -0.01) &
                (df['close'] < df['ma_fast']) &
                (df['volume_trend'] < 0) &
                (df['volatility_regime'] < 2)
            )
            
            short_condition2 = (
                (df['momentum'] < self.config.momentum_threshold_short * 1.5) &
                (df['volume_ratio'] > self.config.min_volume_ratio * 1.2) &
                (df['rsi'] > 50) &
                (df['trend_strength'] < 0) &
                (df['momentum_acc'] < 0)
            )
            
            short_condition3 = (
                (df['bb_position'] > 0.8) &
                (df['momentum'] < 0) &
                (df['volume_ratio'] > 1.5) &
                (df['rsi'] > 60)
            )
            
            # 分配信号（做空侧重）
            np.random.seed(42)  # 可重复性
            random_bias = np.random.random(len(df))
            
            # 做多信号（需要随机偏置 > short_bias）
            long_mask = ((long_condition1 | long_condition2 | long_condition3) & 
                        (random_bias > self.current_short_bias))
            df.loc[long_mask, 'signal'] = 'long'
            
            # 做空信号（需要随机偏置 <= short_bias）
            short_mask = ((short_condition1 | short_condition2 | short_condition3) & 
                         (random_bias <= self.current_short_bias))
            df.loc[short_mask, 'signal'] = 'short'
            
            # 打印条件满足情况
            logger.info("=" * 60)
            logger.info("信号条件诊断")
            logger.info("=" * 60)
            logger.info(f"数据长度: {len(df)}")
            logger.info(f"动态做空侧重: {self.current_short_bias:.2f}")
            logger.info(f"做多条件1满足: {long_condition1.sum()} 行")
            logger.info(f"做多条件2满足: {long_condition2.sum()} 行")
            logger.info(f"做多条件3满足: {long_condition3.sum()} 行")
            logger.info(f"做空条件1满足: {short_condition1.sum()} 行")
            logger.info(f"做空条件2满足: {short_condition2.sum()} 行")
            logger.info(f"做空条件3满足: {short_condition3.sum()} 行")
            logger.info(f"随机偏置 > short_bias: {(random_bias > self.current_short_bias).sum()} 行")
            logger.info(f"随机偏置 <= short_bias: {(random_bias <= self.current_short_bias).sum()} 行")
            logger.info(f"原始做多信号: {(df['signal'] == 'long').sum()} 行")
            logger.info(f"原始做空信号: {(df['signal'] == 'short').sum()} 行")
            
            # 打印最新5行的详细情况
            logger.info("\n最新5行详细数据:")
            for i in range(-5, 0):
                idx = df.index[i] if len(df) >= 5 else df.index[i]
                row = df.loc[idx]
                logger.info(f"第{idx}行: 价格={row['close']:.2f}, 动量={row['momentum']:.3%}, "
                          f"成交量比={row['volume_ratio']:.2f}, RSI={row['rsi']:.1f}, "
                          f"趋势强度={row['trend_strength']}, 信号={row['signal']}")
            
            # 计算信号强度（简化版）
            df = self._calculate_signal_strength(df)
            
            # 过滤信号
            df = self._filter_signals(df)
            
            # 最终统计
            long_count = (df['signal'] == 'long').sum()
            short_count = (df['signal'] == 'short').sum()
            logger.info(f"\n最终信号统计: 做多={long_count}, 做空={short_count}")
            logger.info(f"最新信号: {df['signal'].iloc[-1]}, 强度: {df['signal_strength'].iloc[-1]:.1f}")
            
        except Exception as e:
            logger.error(f"计算信号时出错: {e}", exc_info=True)
        
        return df
    
    def _calculate_signal_strength(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算信号强度（简化版）"""
        df['signal_strength'] = 0.0
        
        # 动量分数
        df.loc[df['signal'] == 'long', 'momentum_score'] = np.clip(
            df['momentum'] / 0.015 * 100, 0, 100
        )
        df.loc[df['signal'] == 'short', 'momentum_score'] = np.clip(
            abs(df['momentum']) / 0.015 * 100, 0, 100
        )
        
        # 成交量分数
        df['volume_score'] = np.clip(
            (df['volume_ratio'] - 1) * 50, 0, 100
        )
        
        # RSI分数
        df.loc[df['signal'] == 'long', 'rsi_score'] = np.clip(
            (70 - df['rsi']) / 40 * 100, 0, 100
        )
        df.loc[df['signal'] == 'short', 'rsi_score'] = np.clip(
            (df['rsi'] - 30) / 40 * 100, 0, 100
        )
        
        # 趋势分数
        df.loc[df['signal'] == 'long', 'trend_score'] = np.clip(
            df['trend_strength'] * 50 + 50, 0, 100
        )
        df.loc[df['signal'] == 'short', 'trend_score'] = np.clip(
            (-df['trend_strength']) * 50 + 50, 0, 100
        )
        
        # 布林带分数
        df.loc[df['signal'] == 'long', 'bb_score'] = np.clip(
            (1 - df['bb_position']) * 100, 0, 100
        )
        df.loc[df['signal'] == 'short', 'bb_score'] = np.clip(
            df['bb_position'] * 100, 0, 100
        )
        
        # 波动率分数
        df['volatility_score'] = np.clip(
            (0.03 - df['atr_pct']) / 0.03 * 100, 0, 100
        )
        
        # 综合分数
        for idx, row in df.iterrows():
            if row['signal'] in ['long', 'short']:
                total_score = 0
                total_score += row.get('momentum_score', 0) * self.signal_strength_weights['momentum']
                total_score += row.get('volume_score', 0) * self.signal_strength_weights['volume']
                total_score += row.get('rsi_score', 0) * self.signal_strength_weights['rsi']
                total_score += row.get('trend_score', 0) * self.signal_strength_weights['trend']
                total_score += row.get('bb_score', 0) * self.signal_strength_weights['bb']
                total_score += row.get('volatility_score', 0) * self.signal_strength_weights['volatility']
                # 多时间框架和舆情分数暂时设为50（中性）
                total_score += 50 * (self.signal_strength_weights['multi_timeframe'] + self.signal_strength_weights['sentiment'])
                df.at[idx, 'signal_strength'] = total_score
        
        return df
    
    def _filter_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """过滤信号"""
        original_signals = (df['signal'] != 'hold').sum()
        
        # 强度过滤
        threshold = self.config.signal_strength_threshold
        strength_filtered = (df['signal'] != 'hold') & (df['signal_strength'] <= threshold)
        strength_filtered_count = strength_filtered.sum()
        df.loc[strength_filtered, 'signal'] = 'hold'
        
        # 波动率过滤
        df.loc[df['atr_pct'] > self.config.max_atr_pct, 'signal'] = 'hold'
        
        # 成交量确认
        df.loc[df['volume_ratio'] < self.config.min_volume_ratio, 'signal'] = 'hold'
        
        # 打印过滤详情
        logger.info("\n过滤详情:")
        logger.info(f"强度过滤 (<={threshold}): {strength_filtered_count} 个信号")
        logger.info(f"波动率过滤 (> {self.config.max_atr_pct:.3%}): {(df['atr_pct'] > self.config.max_atr_pct).sum()} 行")
        logger.info(f"成交量过滤 (< {self.config.min_volume_ratio}): {(df['volume_ratio'] < self.config.min_volume_ratio).sum()} 行")
        
        return df

def main():
    """主诊断函数"""
    logger.info("开始诊断策略不开仓问题")
    
    # 加载配置
    config = load_config()
    
    # 初始化交易所（测试网）
    exchange = ccxt.okx({
        'apiKey': config.api_key,
        'secret': config.api_secret,
        'password': config.api_password,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
            'adjustForTimeDifference': True,
        },
        'proxies': {},
    })
    
    # 设置为测试网
    if config.testnet:
        exchange.set_sandbox_mode(True)
        logger.info("使用测试网模式")
    
    # 获取市场数据
    logger.info(f"获取 {config.symbol} {config.timeframe} OHLCV数据...")
    ohlcv = exchange.fetch_ohlcv(config.symbol, timeframe=config.timeframe, limit=200)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    logger.info(f"获取到 {len(df)} 条数据，时间范围: {df.index[0]} 到 {df.index[-1]}")
    
    # 初始化信号生成器
    signal_gen = OptimizedSignalGenerator(config, exchange)
    
    # 设置舆情分数（模拟）
    signal_gen.current_sentiment_score = -0.56
    signal_gen.current_short_bias = 0.67
    
    # 计算信号
    df = signal_gen.calculate_signals(df)
    
    logger.info("\n" + "="*60)
    logger.info("诊断完成")
    logger.info("="*60)

if __name__ == '__main__':
    main()