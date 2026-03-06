#!/usr/bin/env python3
"""
末日战车策略 - 机器学习数据收集器
为机器学习信号评分收集和准备训练数据
"""

import os
import sys
import time
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import warnings
warnings.filterwarnings('ignore')

# 导入策略模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from okx_doomsday_optimized_v2 import Config, OptimizedSignalGenerator

print("=" * 70)
print("🤖 末日战车策略 - 机器学习数据收集器")
print("=" * 70)


class MLDataCollector:
    """机器学习数据收集器"""
    
    def __init__(self, config: Config, data_dir: str = "ml_data"):
        self.config = config
        self.data_dir = data_dir
        self.logger = logging.getLogger(__name__)
        
        # 创建数据目录
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        
        # 数据文件
        self.trades_file = os.path.join(data_dir, "trades.csv")
        self.signals_file = os.path.join(data_dir, "signals.csv")
        self.market_file = os.path.join(data_dir, "market_data.csv")
        self.features_file = os.path.join(data_dir, "features.csv")
        self.labels_file = os.path.join(data_dir, "labels.csv")
        
        # 初始化数据存储
        self.trades_data = []
        self.signals_data = []
        self.market_data = []
        self.features_data = []
        
        # 数据收集状态
        self.start_time = datetime.now()
        self.data_collection_enabled = True
        
        self.logger.info(f"机器学习数据收集器初始化完成，数据目录: {data_dir}")
    
    def collect_trade_data(self, trade_info: Dict[str, Any]):
        """收集交易数据"""
        if not self.data_collection_enabled:
            return
        
        try:
            # 基础交易信息
            trade_record = {
                'timestamp': datetime.now().isoformat(),
                'trade_id': trade_info.get('id', f"trade_{len(self.trades_data)}"),
                'position_type': trade_info.get('position_type', 'unknown'),  # long/short
                'entry_price': trade_info.get('entry_price', 0),
                'exit_price': trade_info.get('exit_price', 0),
                'entry_time': trade_info.get('entry_time', ''),
                'exit_time': trade_info.get('exit_time', ''),
                'position_size': trade_info.get('position_size', 0),
                'pnl_pct': trade_info.get('pnl_pct', 0),  # 盈亏百分比
                'pnl_amount': trade_info.get('pnl_amount', 0),  # 盈亏金额
                'duration_minutes': trade_info.get('duration_minutes', 0),
                'exit_reason': trade_info.get('exit_reason', 'unknown'),  # 止盈/止损/手动等
                'signal_strength': trade_info.get('signal_strength', 0),
                'stop_loss_pct': trade_info.get('stop_loss_pct', 0),
                'take_profit_pct': trade_info.get('take_profit_pct', 0),
                'volatility_atr': trade_info.get('volatility_atr', 0),
                'trend_direction': trade_info.get('trend_direction', 0),
                'sentiment_score': trade_info.get('sentiment_score', 0),
            }
            
            # 标签：交易是否成功（1=盈利，0=亏损）
            trade_record['success_label'] = 1 if trade_record['pnl_pct'] > 0 else 0
            
            # 标签：交易质量评分（0-100）
            trade_record['quality_label'] = self._calculate_trade_quality(trade_record)
            
            self.trades_data.append(trade_record)
            
            # 定期保存
            if len(self.trades_data) % 10 == 0:
                self._save_trades_data()
            
            self.logger.debug(f"交易数据收集: {trade_record['trade_id']}, 盈亏: {trade_record['pnl_pct']:.2f}%")
            
        except Exception as e:
            self.logger.error(f"收集交易数据失败: {e}")
    
    def collect_signal_data(self, signal_info: Dict[str, Any]):
        """收集信号数据"""
        if not self.data_collection_enabled:
            return
        
        try:
            signal_record = {
                'timestamp': datetime.now().isoformat(),
                'signal_id': signal_info.get('id', f"signal_{len(self.signals_data)}"),
                'signal_type': signal_info.get('signal', 'hold'),  # long/short/hold
                'price': signal_info.get('price', 0),
                'signal_strength': signal_info.get('signal_strength', 0),
                'momentum_score': signal_info.get('momentum_score', 0),
                'volume_score': signal_info.get('volume_score', 0),
                'rsi_score': signal_info.get('rsi_score', 0),
                'trend_score': signal_info.get('trend_score', 0),
                'bb_score': signal_info.get('bb_score', 0),
                'volatility_score': signal_info.get('volatility_score', 0),
                'multi_timeframe_score': signal_info.get('multi_timeframe_score', 0),
                'sentiment_score': signal_info.get('sentiment_score', 0),
                'atr_pct': signal_info.get('atr_pct', 0),
                'volume_ratio': signal_info.get('volume_ratio', 0),
                'rsi_value': signal_info.get('rsi_value', 50),
                'trend_strength': signal_info.get('trend_strength', 0),
                'bb_position': signal_info.get('bb_position', 0.5),
                'higher_timeframe_trend': signal_info.get('higher_timeframe_trend', 0),
                'market_condition': signal_info.get('market_condition', 'neutral'),  # trending/ranging/volatile
                'executed': signal_info.get('executed', False),  # 信号是否被执行
                'trade_result_pct': signal_info.get('trade_result_pct', 0),  # 如果执行了，交易结果
            }
            
            # 标签：信号质量（1=好信号，0=坏信号）
            if signal_record['executed']:
                signal_record['signal_quality_label'] = 1 if signal_record['trade_result_pct'] > 0 else 0
            else:
                # 对于未执行的信号，我们可以用后续价格变化来判断
                signal_record['signal_quality_label'] = None
            
            self.signals_data.append(signal_record)
            
            # 定期保存
            if len(self.signals_data) % 20 == 0:
                self._save_signals_data()
            
            self.logger.debug(f"信号数据收集: {signal_record['signal_id']}, 强度: {signal_record['signal_strength']:.1f}")
            
        except Exception as e:
            self.logger.error(f"收集信号数据失败: {e}")
    
    def collect_market_data(self, market_info: Dict[str, Any]):
        """收集市场数据"""
        if not self.data_collection_enabled:
            return
        
        try:
            market_record = {
                'timestamp': datetime.now().isoformat(),
                'price': market_info.get('price', 0),
                'volume': market_info.get('volume', 0),
                'atr_pct': market_info.get('atr_pct', 0),
                'rsi': market_info.get('rsi', 50),
                'momentum_5m': market_info.get('momentum_5m', 0),
                'momentum_15m': market_info.get('momentum_15m', 0),
                'momentum_1h': market_info.get('momentum_1h', 0),
                'volume_ratio': market_info.get('volume_ratio', 1),
                'trend_5m': market_info.get('trend_5m', 0),
                'trend_1h': market_info.get('trend_1h', 0),
                'volatility_rank': market_info.get('volatility_rank', 0),  # 0-100
                'market_regime': market_info.get('market_regime', 'neutral'),  # uptrend/downtrend/ranging
                'sentiment_index': market_info.get('sentiment_index', 0),  # -1到+1
                'fear_greed_index': market_info.get('fear_greed_index', 50),
                'support_level': market_info.get('support_level', 0),
                'resistance_level': market_info.get('resistance_level', 0),
                'market_depth_bid': market_info.get('market_depth_bid', 0),
                'market_depth_ask': market_info.get('market_depth_ask', 0),
            }
            
            self.market_data.append(market_record)
            
            # 定期保存
            if len(self.market_data) % 50 == 0:
                self._save_market_data()
            
        except Exception as e:
            self.logger.error(f"收集市场数据失败: {e}")
    
    def extract_features(self, trade_data: pd.DataFrame = None, signal_data: pd.DataFrame = None):
        """从原始数据中提取特征"""
        try:
            features = []
            
            # 如果提供了数据，使用提供的数据
            if trade_data is not None and not trade_data.empty:
                trades_df = trade_data
            elif self.trades_data:
                trades_df = pd.DataFrame(self.trades_data)
            else:
                self.logger.warning("没有交易数据可用于特征提取")
                trades_df = pd.DataFrame()
            
            if signal_data is not None and not signal_data.empty:
                signals_df = signal_data
            elif self.signals_data:
                signals_df = pd.DataFrame(self.signals_data)
            else:
                self.logger.warning("没有信号数据可用于特征提取")
                signals_df = pd.DataFrame()
            
            # 交易特征
            if not trades_df.empty:
                for _, trade in trades_df.iterrows():
                    trade_features = {
                        'feature_type': 'trade',
                        'trade_id': trade.get('trade_id', ''),
                        'position_type': 1 if trade.get('position_type') == 'long' else -1,
                        'signal_strength': trade.get('signal_strength', 0),
                        'volatility_atr': trade.get('volatility_atr', 0),
                        'trend_direction': trade.get('trend_direction', 0),
                        'sentiment_score': trade.get('sentiment_score', 0),
                        'stop_loss_pct': trade.get('stop_loss_pct', 0),
                        'take_profit_pct': trade.get('take_profit_pct', 0),
                        'duration_minutes': trade.get('duration_minutes', 0),
                        'entry_rsi': trade.get('entry_rsi', 50),
                        'entry_volume_ratio': trade.get('entry_volume_ratio', 1),
                        'entry_bb_position': trade.get('entry_bb_position', 0.5),
                        'market_regime': self._encode_market_regime(trade.get('market_regime', 'neutral')),
                    }
                    
                    # 时间特征
                    entry_time = pd.to_datetime(trade.get('entry_time', ''))
                    if pd.notnull(entry_time):
                        trade_features['entry_hour'] = entry_time.hour
                        trade_features['entry_day_of_week'] = entry_time.dayofweek
                    
                    features.append(trade_features)
            
            # 信号特征
            if not signals_df.empty:
                for _, signal in signals_df.iterrows():
                    signal_features = {
                        'feature_type': 'signal',
                        'signal_id': signal.get('signal_id', ''),
                        'signal_type': 1 if signal.get('signal_type') == 'long' else -1,
                        'signal_strength': signal.get('signal_strength', 0),
                        'momentum_score': signal.get('momentum_score', 0),
                        'volume_score': signal.get('volume_score', 0),
                        'rsi_score': signal.get('rsi_score', 0),
                        'trend_score': signal.get('trend_score', 0),
                        'bb_score': signal.get('bb_score', 0),
                        'volatility_score': signal.get('volatility_score', 0),
                        'multi_timeframe_score': signal.get('multi_timeframe_score', 0),
                        'sentiment_score': signal.get('sentiment_score', 0),
                        'atr_pct': signal.get('atr_pct', 0),
                        'volume_ratio': signal.get('volume_ratio', 0),
                        'rsi_value': signal.get('rsi_value', 50),
                        'trend_strength': signal.get('trend_strength', 0),
                        'bb_position': signal.get('bb_position', 0.5),
                        'higher_timeframe_trend': signal.get('higher_timeframe_trend', 0),
                        'market_condition': self._encode_market_condition(signal.get('market_condition', 'neutral')),
                    }
                    
                    features.append(signal_features)
            
            # 保存特征
            if features:
                features_df = pd.DataFrame(features)
                features_df.to_csv(self.features_file, mode='a', header=not os.path.exists(self.features_file), index=False)
                self.logger.info(f"特征提取完成，保存{len(features)}个特征到 {self.features_file}")
                
                return features_df
            else:
                self.logger.warning("没有提取到任何特征")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"特征提取失败: {e}")
            return pd.DataFrame()
    
    def prepare_training_data(self, min_samples: int = 100):
        """准备训练数据"""
        try:
            # 加载数据
            trades_df = self._load_trades_data()
            signals_df = self._load_signals_data()
            
            if trades_df.empty and signals_df.empty:
                self.logger.warning("没有足够的数据准备训练数据")
                return None, None
            
            # 提取特征
            features_df = self.extract_features(trades_df, signals_df)
            
            if features_df.empty:
                self.logger.warning("特征数据为空")
                return None, None
            
            # 准备标签
            labels = []
            
            # 从交易数据获取标签
            if not trades_df.empty:
                for _, trade in trades_df.iterrows():
                    if 'success_label' in trade:
                        labels.append({
                            'id': trade.get('trade_id'),
                            'label_type': 'trade_success',
                            'label_value': trade.get('success_label', 0),
                            'label_quality': trade.get('quality_label', 50)
                        })
            
            # 从信号数据获取标签
            if not signals_df.empty:
                for _, signal in signals_df.iterrows():
                    if 'signal_quality_label' in signal and pd.notnull(signal['signal_quality_label']):
                        labels.append({
                            'id': signal.get('signal_id'),
                            'label_type': 'signal_quality',
                            'label_value': signal.get('signal_quality_label', 0),
                            'label_quality': 75  # 默认质量
                        })
            
            # 保存标签
            if labels:
                labels_df = pd.DataFrame(labels)
                labels_df.to_csv(self.labels_file, mode='a', header=not os.path.exists(self.labels_file), index=False)
                self.logger.info(f"标签准备完成，保存{len(labels)}个标签到 {self.labels_file}")
                
                return features_df, labels_df
            else:
                self.logger.warning("没有有效的标签数据")
                return features_df, pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"准备训练数据失败: {e}")
            return None, None
    
    def generate_ml_report(self):
        """生成机器学习数据报告"""
        try:
            trades_df = self._load_trades_data()
            signals_df = self._load_signals_data()
            features_df = self._load_features_data()
            labels_df = self._load_labels_data()
            
            report = {
                'generated_at': datetime.now().isoformat(),
                'data_collection_duration_days': (datetime.now() - self.start_time).days,
                'trades_count': len(trades_df),
                'signals_count': len(signals_df),
                'features_count': len(features_df),
                'labels_count': len(labels_df),
                'trade_success_rate': None,
                'signal_success_rate': None,
                'data_quality_score': self._calculate_data_quality_score(trades_df, signals_df),
            }
            
            # 计算成功率
            if not trades_df.empty and 'success_label' in trades_df.columns:
                success_count = trades_df['success_label'].sum()
                report['trade_success_rate'] = success_count / len(trades_df) * 100
            
            if not signals_df.empty and 'signal_quality_label' in signals_df.columns:
                valid_signals = signals_df.dropna(subset=['signal_quality_label'])
                if not valid_signals.empty:
                    success_count = valid_signals['signal_quality_label'].sum()
                    report['signal_success_rate'] = success_count / len(valid_signals) * 100
            
            # 保存报告
            report_file = os.path.join(self.data_dir, "ml_report.json")
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"机器学习数据报告已生成: {report_file}")
            
            # 打印报告摘要
            print("\n" + "=" * 70)
            print("📊 机器学习数据收集报告")
            print("=" * 70)
            print(f"数据收集时长: {report['data_collection_duration_days']}天")
            print(f"交易数据: {report['trades_count']}条")
            print(f"信号数据: {report['signals_count']}条")
            print(f"特征数据: {report['features_count']}条")
            print(f"标签数据: {report['labels_count']}条")
            if report['trade_success_rate'] is not None:
                print(f"交易成功率: {report['trade_success_rate']:.1f}%")
            if report['signal_success_rate'] is not None:
                print(f"信号成功率: {report['signal_success_rate']:.1f}%")
            print(f"数据质量评分: {report['data_quality_score']:.1f}/100")
            print("=" * 70)
            
            return report
            
        except Exception as e:
            self.logger.error(f"生成机器学习报告失败: {e}")
            return {}
    
    # ==================== 辅助方法 ====================
    
    def _calculate_trade_quality(self, trade_record: Dict) -> float:
        """计算交易质量评分（0-100）"""
        try:
            quality = 50  # 基础分
            
            # 盈利加分
            if trade_record['pnl_pct'] > 0:
                quality += min(30, trade_record['pnl_pct'] * 10)  # 每1%收益加10分，最多30分
            
            # 风险控制加分（止损合理）
            if trade_record['stop_loss_pct'] > 0:
                # 止损在3-8%之间为合理
                if 0.03 <= trade_record['stop_loss_pct'] <= 0.08:
                    quality += 10
            
            # 信号强度加分
            quality += min(20, trade_record['signal_strength'] / 5)  # 每5分强度加1分，最多20分
            
            # 持仓时间合理加分（10分钟到4小时）
            duration = trade_record.get('duration_minutes', 0)
            if 10 <= duration <= 240:
                quality += 10
            
            return min(100, max(0, quality))
        except:
            return 50
    
    def _encode_market_regime(self, regime: str) -> int:
        """编码市场状态"""
        regimes = {
            'uptrend': 2,
            'downtrend': -2,
            'ranging': 0,
            'volatile': 1,
            'neutral': 0
        }
        return regimes.get(regime, 0)
    
    def _encode_market_condition(self, condition: str) -> int:
        """编码市场条件"""
        conditions = {
            'trending': 2,
            'ranging': 0,
            'volatile': 1,
            'neutral': 0
        }
        return conditions.get(condition, 0)
    
    def _calculate_data_quality_score(self, trades_df: pd.DataFrame, signals_df: pd.DataFrame) -> float:
        """计算数据质量评分"""
        score = 0
        
        # 数据完整性
        if not trades_df.empty:
            completeness = trades_df.notnull().mean().mean()
            score += completeness * 40  # 最多40分
        
        if not signals_df.empty:
            completeness = signals_df.notnull().mean().mean()
            score += completeness * 30  # 最多30分
        
        # 数据多样性
        if not trades_df.empty and len(trades_df) >= 50:
            score += 15  # 交易数据量足够
        
        if not signals_df.empty and len(signals_df) >= 100:
            score += 15  # 信号数据量足够
        
        return min(100, score)
    
    def _save_trades_data(self):
        """保存交易数据"""
        if self.trades_data:
            df = pd.DataFrame(self.trades_data)
            df.to_csv(self.trades_file, mode='a', header=not os.path.exists(self.trades_file), index=False)
    
    def _save_signals_data(self):
        """保存信号数据"""
        if self.signals_data:
            df = pd.DataFrame(self.signals_data)
            df.to_csv(self.signals_file, mode='a', header=not os.path.exists(self.signals_file), index=False)
    
    def _save_market_data(self):
        """保存市场数据"""
        if self.market_data:
            df = pd.DataFrame(self.market_data)
            df.to_csv(self.market_file, mode='a', header=not os.path.exists(self.market_file), index=False)
    
    def _load_trades_data(self) -> pd.DataFrame:
        """加载交易数据"""
        if os.path.exists(self.trades_file):
            return pd.read_csv(self.trades_file)
        return pd.DataFrame()
    
    def _load_signals_data(self) -> pd.DataFrame:
        """加载信号数据"""
        if os.path.exists(self.signals_file):
            return pd.read_csv(self.signals_file)
        return pd.DataFrame()
    
    def _load_market_data(self) -> pd.DataFrame:
        """加载市场数据"""
        if os.path.exists(self.market_file):
            return pd.read_csv(self.market_file)
        return pd.DataFrame()
    
    def _load_features_data(self) -> pd.DataFrame:
        """加载特征数据"""
        if os.path.exists(self.features_file):
            return pd.read_csv(self.features_file)
        return pd.DataFrame()
    
    def _load_labels_data(self) -> pd.DataFrame:
        """加载标签数据"""
        if os.path.exists(self.labels_file):
            return pd.read_csv(self.labels_file)
        return pd.DataFrame()
    
    def stop_collection(self):
        """停止数据收集"""
        self.data_collection_enabled = False
        
        # 保存所有数据
        self._save_trades_data()
        self._save_signals_data()
        self._save_market_data()
        
        self.logger.info("机器学习数据收集已停止")


# ==================== 主函数 ====================
def main():
    """主函数 - 测试数据收集器"""
    print("🤖 机器学习数据收集器测试")
    print("-" * 70)
    
    # 创建测试配置
    config = Config(
        symbol="ETH-USDT-SWAP",
        api_key="", api_secret="", api_password="",
        signal_strength_threshold=22,
        ml_signal_scoring=True
    )
    
    # 初始化数据收集器
    collector = MLDataCollector(config, data_dir="ml_data_test")
    
    # 生成测试数据
    print("生成测试数据...")
    
    # 模拟10个交易
    for i in range(10):
        trade_info = {
            'id': f"test_trade_{i}",
            'position_type': 'long' if i % 2 == 0 else 'short',
            'entry_price': 2000 + np.random.uniform(-100, 100),
            'exit_price': 2000 + np.random.uniform(-50, 150),
            'entry_time': (datetime.now() - timedelta(hours=i)).isoformat(),
            'exit_time': datetime.now().isoformat(),
            'position_size': np.random.uniform(0.1, 1.0),
            'pnl_pct': np.random.uniform(-10, 15),
            'pnl_amount': np.random.uniform(-200, 300),
            'duration_minutes': np.random.randint(5, 240),
            'exit_reason': np.random.choice(['止盈', '止损', '手动平仓']),
            'signal_strength': np.random.uniform(20, 80),
            'stop_loss_pct': np.random.uniform(0.03, 0.08),
            'take_profit_pct': np.random.uniform(0.06, 0.12),
            'volatility_atr': np.random.uniform(0.01, 0.04),
            'trend_direction': np.random.choice([-1, 0, 1]),
            'sentiment_score': np.random.uniform(-0.5, 0.5),
            'market_regime': np.random.choice(['uptrend', 'downtrend', 'ranging']),
        }
        collector.collect_trade_data(trade_info)
    
    # 模拟20个信号
    for i in range(20):
        signal_info = {
            'id': f"test_signal_{i}",
            'signal': 'long' if i % 3 == 0 else 'short',
            'price': 2000 + np.random.uniform(-50, 50),
            'signal_strength': np.random.uniform(15, 85),
            'momentum_score': np.random.uniform(0, 100),
            'volume_score': np.random.uniform(0, 100),
            'rsi_score': np.random.uniform(0, 100),
            'trend_score': np.random.uniform(0, 100),
            'bb_score': np.random.uniform(0, 100),
            'volatility_score': np.random.uniform(0, 100),
            'multi_timeframe_score': np.random.uniform(0, 100),
            'sentiment_score': np.random.uniform(0, 100),
            'atr_pct': np.random.uniform(0.01, 0.05),
            'volume_ratio': np.random.uniform(0.8, 3.0),
            'rsi_value': np.random.uniform(20, 80),
            'trend_strength': np.random.uniform(-2, 2),
            'bb_position': np.random.uniform(0, 1),
            'higher_timeframe_trend': np.random.choice([-1, 0, 1]),
            'market_condition': np.random.choice(['trending', 'ranging', 'volatile']),
            'executed': i < 10,  # 前10个信号执行了
            'trade_result_pct': np.random.uniform(-5, 10) if i < 10 else 0,
        }
        collector.collect_signal_data(signal_info)
    
    # 准备训练数据
    print("\n准备训练数据...")
    features_df, labels_df = collector.prepare_training_data()
    
    # 生成报告
    print("\n生成数据报告...")
    report = collector.generate_ml_report()
    
    # 停止收集
    collector.stop_collection()
    
    print("\n✅ 机器学习数据收集器测试完成！")
    print("数据已保存到 ml_data_test/ 目录")
    print("=" * 70)


if __name__ == "__main__":
    main()