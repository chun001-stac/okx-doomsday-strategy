#!/usr/bin/env python3
"""
多时间框架验证脚本
测试1h趋势数据对5m信号的确认效果
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
print("📊 多时间框架验证测试")
print("验证1h趋势数据对5m信号的确认效果")
print("=" * 70)


class MultiTimeframeValidator:
    """多时间框架验证器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 结果存储
        self.validation_results = []
        self.signal_stats = {
            'total_signals': 0,
            'filtered_signals': 0,
            'confirmed_signals': 0,
            'rejected_signals': 0,
            'confirmed_success_rate': 0,
            'rejected_success_rate': 0,
        }
        
        # 数据缓存
        self.higher_timeframe_data = None
        self.higher_timeframe_last_update = 0
    
    def generate_test_data(self, days: int = 30) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """生成测试数据"""
        print(f"生成{days}天测试数据...")
        
        # 生成5分钟数据
        n_kline_5m = days * 24 * 12  # 5分钟K线数
        n_kline_1h = days * 24       # 1小时K线数
        
        # 时间戳
        start_date = datetime.now() - timedelta(days=days)
        
        # 生成5分钟数据
        timestamps_5m = [start_date + timedelta(minutes=5*i) for i in range(n_kline_5m)]
        
        # 价格序列（带趋势和波动）
        np.random.seed(42)
        base_price = 2000.0
        trend_5m = 0.00002  # 每5分钟趋势
        volatility_5m = 0.005
        
        returns_5m = np.random.normal(trend_5m, volatility_5m, n_kline_5m)
        prices_5m = base_price * np.exp(np.cumsum(returns_5m))
        
        # 生成1小时数据（基于5分钟数据聚合）
        timestamps_1h = [start_date + timedelta(hours=i) for i in range(n_kline_1h)]
        prices_1h = []
        
        for i in range(n_kline_1h):
            start_idx = i * 12
            end_idx = min(start_idx + 12, len(prices_5m))
            if start_idx < len(prices_5m):
                hour_prices = prices_5m[start_idx:end_idx]
                if len(hour_prices) > 0:
                    prices_1h.append(np.mean(hour_prices))
                else:
                    prices_1h.append(prices_5m[-1] if prices_5m else base_price)
        
        # 创建DataFrame
        df_5m = pd.DataFrame({
            'timestamp': timestamps_5m,
            'open': prices_5m * (1 + np.random.uniform(-0.001, 0.001, n_kline_5m)),
            'high': np.maximum(prices_5m, prices_5m * (1 + np.random.uniform(0, 0.002, n_kline_5m))),
            'low': np.minimum(prices_5m, prices_5m * (1 - np.random.uniform(0, 0.002, n_kline_5m))),
            'close': prices_5m,
            'volume': np.random.lognormal(10, 1, n_kline_5m),
        })
        df_5m.set_index('timestamp', inplace=True)
        
        df_1h = pd.DataFrame({
            'timestamp': timestamps_1h[:len(prices_1h)],
            'open': prices_1h,
            'high': np.array(prices_1h) * (1 + np.random.uniform(0, 0.005, len(prices_1h))),
            'low': np.array(prices_1h) * (1 - np.random.uniform(0, 0.005, len(prices_1h))),
            'close': prices_1h,
            'volume': np.random.lognormal(12, 1, len(prices_1h)),
        })
        df_1h.set_index('timestamp', inplace=True)
        
        # 计算1h趋势
        df_1h['ma_fast'] = df_1h['close'].rolling(window=5).mean()
        df_1h['ma_slow'] = df_1h['close'].rolling(window=20).mean()
        df_1h['trend'] = df_1h.apply(
            lambda row: 1 if row['ma_fast'] > row['ma_slow'] else -1 if row['ma_fast'] < row['ma_slow'] else 0,
            axis=1
        )
        
        print(f"✅ 测试数据生成完成:")
        print(f"   5分钟数据: {len(df_5m)}根K线，价格范围: ${df_5m['close'].min():.0f}-${df_5m['close'].max():.0f}")
        print(f"   1小时数据: {len(df_1h)}根K线，最新趋势: {df_1h['trend'].iloc[-1] if 'trend' in df_1h.columns else '未知'}")
        
        return df_5m, df_1h
    
    def validate_multi_timeframe_effect(self, df_5m: pd.DataFrame, df_1h: pd.DataFrame):
        """验证多时间框架效果"""
        print("\n🔬 验证多时间框架确认效果...")
        
        # 复制5分钟数据
        df_test = df_5m.copy()
        
        # 计算技术指标
        df_test = self._calculate_indicators(df_test)
        
        # 生成基础信号（不考虑多时间框架）
        df_test['signal_base'] = 'hold'
        df_test['signal_strength_base'] = 0.0
        
        for i in range(100, len(df_test)):
            row = df_test.iloc[i]
            
            # 基础信号条件
            long_condition = (
                row['momentum'] > self.config.momentum_threshold_long and
                row['volume_ratio'] > self.config.min_volume_ratio and
                row['rsi'] > 30 and row['rsi'] < self.config.rsi_overbought and
                row['atr_pct'] < self.config.max_atr_pct
            )
            
            short_condition = (
                row['momentum'] < self.config.momentum_threshold_short and
                row['volume_ratio'] > self.config.min_volume_ratio and
                row['rsi'] > self.config.rsi_oversold and row['rsi'] < 75 and
                row['atr_pct'] < self.config.max_atr_pct
            )
            
            np.random.seed(i)
            if long_condition and np.random.random() > self.config.short_bias:
                df_test.at[df_test.index[i], 'signal_base'] = 'long'
                strength = 50.0
                strength += min(20, max(0, row['momentum'] / 0.01 * 100))
                strength += min(10, max(0, (row['volume_ratio'] - 1) * 50))
                strength += min(15, max(0, (70 - row['rsi']) / 40 * 100))
                strength = min(100, max(0, strength))
                df_test.at[df_test.index[i], 'signal_strength_base'] = strength
                
            elif short_condition and np.random.random() <= self.config.short_bias:
                df_test.at[df_test.index[i], 'signal_base'] = 'short'
                strength = 50.0
                strength += min(20, max(0, abs(row['momentum']) / 0.01 * 100))
                strength += min(10, max(0, (row['volume_ratio'] - 1) * 50))
                strength += min(15, max(0, (row['rsi'] - 30) / 40 * 100))
                strength = min(100, max(0, strength))
                df_test.at[df_test.index[i], 'signal_strength_base'] = strength
        
        # 应用多时间框架过滤
        df_test['signal_mtf'] = 'hold'
        df_test['signal_strength_mtf'] = 0.0
        df_test['mtf_confirmation'] = False
        df_test['mtf_trend'] = 0
        
        for idx, row in df_test.iterrows():
            if row['signal_base'] != 'hold' and row['signal_strength_base'] >= self.config.signal_strength_threshold:
                # 获取对应时间的1h趋势
                mtf_trend = self._get_higher_timeframe_trend(df_1h, idx)
                df_test.at[idx, 'mtf_trend'] = mtf_trend
                
                signal = row['signal_base']
                strength = row['signal_strength_base']
                
                # 多时间框架确认逻辑
                if (signal == 'long' and mtf_trend > 0) or (signal == 'short' and mtf_trend < 0):
                    # 趋势一致，确认信号
                    df_test.at[idx, 'signal_mtf'] = signal
                    df_test.at[idx, 'signal_strength_mtf'] = strength * (1 + self.config.higher_timeframe_weight)
                    df_test.at[idx, 'mtf_confirmation'] = True
                    self.signal_stats['confirmed_signals'] += 1
                elif (signal == 'long' and mtf_trend < 0) or (signal == 'short' and mtf_trend > 0):
                    # 趋势相反，拒绝信号
                    df_test.at[idx, 'signal_mtf'] = 'hold'
                    df_test.at[idx, 'signal_strength_mtf'] = 0
                    df_test.at[idx, 'mtf_confirmation'] = False
                    self.signal_stats['rejected_signals'] += 1
                else:
                    # 趋势中性，保持原信号但可能调整强度
                    df_test.at[idx, 'signal_mtf'] = signal
                    df_test.at[idx, 'signal_strength_mtf'] = strength
                    df_test.at[idx, 'mtf_confirmation'] = False
        
        # 统计
        base_signals = (df_test['signal_base'] != 'hold').sum()
        filtered_signals = (df_test['signal_mtf'] != 'hold').sum()
        
        self.signal_stats['total_signals'] = base_signals
        self.signal_stats['filtered_signals'] = filtered_signals
        
        print(f"✅ 多时间框架验证完成:")
        print(f"   基础信号: {base_signals}个")
        print(f"   过滤后信号: {filtered_signals}个")
        print(f"   信号过滤率: {(base_signals - filtered_signals)/max(1, base_signals)*100:.1f}%")
        print(f"   确认信号: {self.signal_stats['confirmed_signals']}个")
        print(f"   拒绝信号: {self.signal_stats['rejected_signals']}个")
        
        return df_test
    
    def evaluate_signal_quality(self, df_test: pd.DataFrame):
        """评估信号质量"""
        print("\n📈 评估信号质量...")
        
        # 模拟后续价格变化来判断信号质量
        lookforward_periods = 12  # 1小时后（12根5分钟K线）
        
        results = []
        
        for idx, row in df_test.iterrows():
            if row['signal_base'] != 'hold':
                # 找到当前索引
                current_idx = df_test.index.get_loc(idx)
                if current_idx + lookforward_periods < len(df_test):
                    # 获取后续价格
                    future_prices = df_test.iloc[current_idx:current_idx+lookforward_periods]['close']
                    if len(future_prices) > 0:
                        current_price = row['close']
                        max_price = future_prices.max()
                        min_price = future_prices.min()
                        
                        # 判断信号质量
                        if row['signal_base'] == 'long':
                            # 做多信号：价格上涨为成功
                            price_change = (max_price - current_price) / current_price
                            success = price_change > 0.005  # 上涨0.5%以上为成功
                        else:  # short
                            # 做空信号：价格下跌为成功
                            price_change = (current_price - min_price) / current_price
                            success = price_change > 0.005  # 下跌0.5%以上为成功
                        
                        result = {
                            'timestamp': idx,
                            'signal': row['signal_base'],
                            'signal_strength': row['signal_strength_base'],
                            'mtf_trend': row['mtf_trend'],
                            'mtf_confirmation': row['mtf_confirmation'],
                            'signal_mtf': row['signal_mtf'],
                            'signal_strength_mtf': row['signal_strength_mtf'],
                            'current_price': current_price,
                            'future_max': max_price,
                            'future_min': min_price,
                            'price_change_pct': price_change * 100,
                            'success': success,
                        }
                        
                        results.append(result)
        
        if not results:
            print("⚠️  没有足够的数据评估信号质量")
            return pd.DataFrame()
        
        results_df = pd.DataFrame(results)
        
        # 计算成功率
        base_success_rate = results_df['success'].mean() * 100
        
        # 计算多时间框架确认后的成功率
        confirmed_results = results_df[results_df['mtf_confirmation'] == True]
        confirmed_success_rate = confirmed_results['success'].mean() * 100 if not confirmed_results.empty else 0
        
        # 计算拒绝信号的成功率（如果执行了会怎样）
        rejected_results = results_df[(results_df['mtf_confirmation'] == False) & (results_df['signal_mtf'] == 'hold')]
        rejected_success_rate = rejected_results['success'].mean() * 100 if not rejected_results.empty else 0
        
        # 更新统计
        self.signal_stats['confirmed_success_rate'] = confirmed_success_rate
        self.signal_stats['rejected_success_rate'] = rejected_success_rate
        
        print(f"✅ 信号质量评估完成:")
        print(f"   基础信号成功率: {base_success_rate:.1f}%")
        print(f"   确认信号成功率: {confirmed_success_rate:.1f}%")
        if confirmed_success_rate > base_success_rate:
            print(f"   ✅ 多时间框架确认提升成功率: +{confirmed_success_rate - base_success_rate:.1f}%")
        else:
            print(f"   ⚠️  多时间框架确认未提升成功率: {confirmed_success_rate - base_success_rate:.1f}%")
        
        print(f"   拒绝信号成功率: {rejected_success_rate:.1f}%")
        if rejected_success_rate < base_success_rate:
            print(f"   ✅ 多时间框架拒绝正确过滤低质量信号")
        else:
            print(f"   ⚠️  多时间框架拒绝可能过滤了高质量信号")
        
        return results_df
    
    def generate_validation_report(self, results_df: pd.DataFrame = None):
        """生成验证报告"""
        print("\n📋 生成多时间框架验证报告...")
        
        report = {
            'validation_date': datetime.now().isoformat(),
            'config': {
                'higher_timeframe': self.config.higher_timeframe,
                'higher_timeframe_weight': self.config.higher_timeframe_weight,
                'signal_strength_threshold': self.config.signal_strength_threshold,
                'multi_timeframe_confirmation': self.config.multi_timeframe_confirmation,
            },
            'signal_statistics': self.signal_stats,
            'effectiveness_metrics': {},
            'recommendations': [],
        }
        
        # 计算有效性指标
        if self.signal_stats['total_signals'] > 0:
            report['effectiveness_metrics'] = {
                'signal_filter_rate': (self.signal_stats['total_signals'] - self.signal_stats['filtered_signals']) / self.signal_stats['total_signals'] * 100,
                'confirmation_rate': self.signal_stats['confirmed_signals'] / max(1, self.signal_stats['filtered_signals']) * 100,
                'success_rate_improvement': self.signal_stats['confirmed_success_rate'] - (self.signal_stats['confirmed_success_rate'] + self.signal_stats['rejected_success_rate']) / 2 if self.signal_stats['rejected_success_rate'] > 0 else 0,
                'quality_score': self._calculate_quality_score(),
            }
        
        # 生成建议
        if self.signal_stats['confirmed_success_rate'] > 0:
            improvement = self.signal_stats['confirmed_success_rate'] - self.signal_stats['rejected_success_rate']
            
            if improvement > 5:
                report['recommendations'].append("✅ 多时间框架确认效果显著，建议保持当前配置")
                report['recommendations'].append(f"   确认信号成功率比拒绝信号高{improvement:.1f}%")
            elif improvement > 0:
                report['recommendations'].append("📊 多时间框架确认有效果，但提升有限")
                report['recommendations'].append(f"   确认信号成功率比拒绝信号高{improvement:.1f}%")
                report['recommendations'].append("   考虑调整higher_timeframe_weight参数")
            else:
                report['recommendations'].append("⚠️  多时间框架确认效果不明显")
                report['recommendations'].append("   可能需要重新评估时间框架选择或权重设置")
        
        # 过滤效果建议
        filter_rate = report['effectiveness_metrics'].get('signal_filter_rate', 0)
        if filter_rate > 30:
            report['recommendations'].append(f"⚠️  信号过滤率较高({filter_rate:.1f}%)，可能错过机会")
            report['recommendations'].append("   考虑降低higher_timeframe_weight或signal_strength_threshold")
        elif filter_rate < 10:
            report['recommendations'].append(f"📊 信号过滤率较低({filter_rate:.1f}%)，过滤效果有限")
            report['recommendations'].append("   考虑增加higher_timeframe_weight或使用更严格的时间框架条件")
        
        # 保存报告（处理JSON序列化）
        report_file = "multi_timeframe_validation_report.json"
        
        # 转换为可JSON序列化的格式
        def convert_to_serializable(obj):
            if isinstance(obj, (np.integer, np.int64)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            else:
                return obj
        
        serializable_report = json.loads(json.dumps(report, default=convert_to_serializable))
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 验证报告已保存: {report_file}")
        
        # 打印报告摘要
        print("\n" + "=" * 70)
        print("📊 多时间框架验证报告摘要")
        print("=" * 70)
        print(f"配置:")
        print(f"  更高时间框架: {report['config']['higher_timeframe']}")
        print(f"  时间框架权重: {report['config']['higher_timeframe_weight']}")
        print(f"  信号强度阈值: {report['config']['signal_strength_threshold']}")
        
        print(f"\n信号统计:")
        print(f"  总信号数: {report['signal_statistics']['total_signals']}")
        print(f"  过滤后信号: {report['signal_statistics']['filtered_signals']}")
        print(f"  确认信号: {report['signal_statistics']['confirmed_signals']}")
        print(f"  拒绝信号: {report['signal_statistics']['rejected_signals']}")
        
        print(f"\n成功率:")
        print(f"  确认信号成功率: {report['signal_statistics']['confirmed_success_rate']:.1f}%")
        print(f"  拒绝信号成功率: {report['signal_statistics']['rejected_success_rate']:.1f}%")
        
        if 'effectiveness_metrics' in report:
            print(f"\n有效性指标:")
            print(f"  信号过滤率: {report['effectiveness_metrics'].get('signal_filter_rate', 0):.1f}%")
            print(f"  确认率: {report['effectiveness_metrics'].get('confirmation_rate', 0):.1f}%")
            print(f"  质量评分: {report['effectiveness_metrics'].get('quality_score', 0):.1f}/100")
        
        print(f"\n建议:")
        for rec in report['recommendations']:
            print(f"  {rec}")
        
        print("=" * 70)
        
        return report
    
    # ==================== 辅助方法 ====================
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        # 动量
        df['momentum'] = df['close'].pct_change(periods=5)
        
        # 成交量
        df['volume_ma'] = df['volume'].rolling(window=10).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # RSI
        def calculate_rsi(prices, period=7):
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        
        df['rsi'] = calculate_rsi(df['close'], 7)
        
        # ATR
        df['tr'] = np.maximum(df['high'] - df['low'], 
                             np.maximum(abs(df['high'] - df['close'].shift()), 
                                       abs(df['low'] - df['close'].shift())))
        df['atr'] = df['tr'].rolling(window=14).mean()
        df['atr_pct'] = df['atr'] / df['close']
        
        # 趋势
        df['ma_fast'] = df['close'].rolling(window=5).mean()
        df['ma_medium'] = df['close'].rolling(window=15).mean()
        df['ma_slow'] = df['close'].rolling(window=30).mean()
        
        df['trend_strength'] = df.apply(
            lambda row: 2 if (row['ma_fast'] > row['ma_medium'] > row['ma_slow']) else
            -2 if (row['ma_fast'] < row['ma_medium'] < row['ma_slow']) else 0,
            axis=1
        )
        
        return df
    
    def _get_higher_timeframe_trend(self, df_1h: pd.DataFrame, timestamp) -> int:
        """获取对应时间戳的更高时间框架趋势"""
        try:
            # 找到最近的1h K线
            if timestamp in df_1h.index:
                return df_1h.loc[timestamp, 'trend'] if 'trend' in df_1h.columns else 0
            
            # 找到之前最近的1h K线
            earlier_timestamps = df_1h.index[df_1h.index <= timestamp]
            if len(earlier_timestamps) > 0:
                nearest_timestamp = earlier_timestamps[-1]
                return df_1h.loc[nearest_timestamp, 'trend'] if 'trend' in df_1h.columns else 0
            
            return 0
        except:
            return 0
    
    def _calculate_quality_score(self) -> float:
        """计算质量评分（0-100）"""
        score = 0
        
        # 成功率提升
        improvement = self.signal_stats['confirmed_success_rate'] - self.signal_stats['rejected_success_rate']
        if improvement > 0:
            score += min(40, improvement * 4)  # 每1%提升加4分，最多40分
        
        # 过滤合理性
        filter_rate = (self.signal_stats['total_signals'] - self.signal_stats['filtered_signals']) / max(1, self.signal_stats['total_signals']) * 100
        if 10 <= filter_rate <= 40:
            score += 30  # 过滤率在10-40%之间为合理
        else:
            score += max(0, 30 - abs(filter_rate - 25))  # 距离25%越近分数越高
        
        # 数据充分性
        if self.signal_stats['total_signals'] >= 50:
            score += 15
        
        if self.signal_stats['confirmed_signals'] >= 10:
            score += 15
        
        return min(100, max(0, score))


# ==================== 主函数 ====================
def main():
    """主函数"""
    print("🚀 多时间框架验证测试开始")
    
    # 创建配置
    config = Config(
        symbol="ETH-USDT-SWAP",
        api_key="", api_secret="", api_password="",
        signal_strength_threshold=22,
        multi_timeframe_confirmation=True,
        higher_timeframe="1h",
        higher_timeframe_weight=0.3,
        momentum_threshold_long=0.005,
        momentum_threshold_short=-0.005,
        rsi_overbought=75,
        rsi_oversold=25,
        short_bias=0.75,
        min_volume_ratio=1.2,
        max_atr_pct=0.05,
    )
    
    # 初始化验证器
    validator = MultiTimeframeValidator(config)
    
    # 生成测试数据
    df_5m, df_1h = validator.generate_test_data(days=30)
    
    # 验证多时间框架效果
    df_test = validator.validate_multi_timeframe_effect(df_5m, df_1h)
    
    # 评估信号质量
    results_df = validator.evaluate_signal_quality(df_test)
    
    # 生成验证报告
    report = validator.generate_validation_report(results_df)
    
    print("\n✅ 多时间框架验证测试完成！")
    print("=" * 70)
    print("下一步建议:")
    print("1. 如果验证效果良好，可在实盘中启用multi_timeframe_confirmation")
    print("2. 根据验证结果调整higher_timeframe_weight参数")
    print("3. 考虑测试其他时间框架组合（如4h/1h, 1h/15m等）")
    print("4. 定期重新验证以适应市场变化")
    print("=" * 70)


if __name__ == "__main__":
    main()