#!/usr/bin/env python3
"""
末日战车策略参数调优
基于30天回测结果，优化6个关键参数
"""

import itertools
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

print("=" * 70)
print("🔧 末日战车策略参数调优")
print("=" * 70)

# ==================== 生成模拟数据（30天） ====================
print("📊 生成30天模拟数据...")

np.random.seed(42)
n_kline = 30 * 24 * 12  # 8640根5分钟K线
start_date = datetime.now() - timedelta(days=30)
timestamps = [start_date + timedelta(minutes=5*i) for i in range(n_kline)]

# ETH价格模拟
base_price = 2000.0
trend = 0.00002
volatility = 0.005

returns = np.random.normal(trend, volatility, n_kline)
prices = base_price * np.exp(np.cumsum(returns))

# OHLCV数据
opens = prices * (1 + np.random.uniform(-0.001, 0.001, n_kline))
highs = np.maximum(opens, prices) * (1 + np.random.uniform(0, 0.002, n_kline))
lows = np.minimum(opens, prices) * (1 - np.random.uniform(0, 0.002, n_kline))
closes = prices
volumes = np.random.lognormal(10, 1, n_kline)

df = pd.DataFrame({
    'timestamp': timestamps,
    'open': opens,
    'high': highs,
    'low': lows,
    'close': closes,
    'volume': volumes
})
df.set_index('timestamp', inplace=True)

# 技术指标计算
df['momentum'] = df['close'].pct_change(periods=5)
df['volume_ma'] = df['volume'].rolling(window=10).mean()
df['volume_ratio'] = df['volume'] / df['volume_ma']
df['rsi'] = 100 - (100 / (1 + (df['close'].diff().where(lambda x: x > 0, 0).rolling(7).mean() / 
                              df['close'].diff().where(lambda x: x < 0, 0).abs().rolling(7).mean())))
df['atr'] = np.maximum(df['high'] - df['low'], 
                      np.maximum(abs(df['high'] - df['close'].shift()), 
                                abs(df['low'] - df['close'].shift()))).rolling(14).mean()
df['atr_pct'] = df['atr'] / df['close']

print(f"✅ 数据准备完成: {len(df)}根K线")

# ==================== 参数调优定义 ====================
class ParameterGrid:
    """参数网格定义"""
    
    def __init__(self):
        # 基础参数（固定）
        self.base_params = {
            'base_position_size_pct': 0.30,
            'min_position_size_pct': 0.05,
            'max_position_size_pct': 0.30,
            'fee_rate': 0.001,
            'max_atr_pct': 0.05,
            'min_volume_ratio': 1.2,
            'rsi_period': 7
        }
        
        # 待调优参数范围
        self.param_ranges = {
            # 优化点1：信号强度阈值
            'signal_strength_threshold': [15, 20, 25, 30],
            
            # 优化点2：止损止盈
            'base_stoploss_pct': [0.04, 0.05, 0.06],
            'base_takeprofit_pct': [0.08, 0.09, 0.10],
            
            # 优化点3：动态仓位指数
            'strength_to_position_power': [1.2, 1.5, 1.8],
            
            # 动量阈值
            'momentum_threshold_long': [0.003, 0.005, 0.007],
            'momentum_threshold_short': [-0.007, -0.005, -0.003],
            
            # RSI过滤
            'rsi_overbought': [70, 75, 80],
            'rsi_oversold': [20, 25, 30],
            
            # 做空侧重
            'short_bias': [0.65, 0.70, 0.75, 0.80],
            
            # 趋势确认周期
            'trend_confirmation_period': [1, 2, 3]
        }
        
        # 优先调优组合（关键参数）
        self.priority_combinations = [
            # 组合1：保守型（低风险）
            {
                'signal_strength_threshold': 25,
                'base_stoploss_pct': 0.04,
                'base_takeprofit_pct': 0.10,
                'strength_to_position_power': 1.2,
                'momentum_threshold_long': 0.007,
                'momentum_threshold_short': -0.007,
                'rsi_overbought': 80,
                'rsi_oversold': 20,
                'short_bias': 0.70,
                'trend_confirmation_period': 2
            },
            # 组合2：平衡型（推荐）
            {
                'signal_strength_threshold': 22,
                'base_stoploss_pct': 0.05,
                'base_takeprofit_pct': 0.09,
                'strength_to_position_power': 1.5,
                'momentum_threshold_long': 0.005,
                'momentum_threshold_short': -0.005,
                'rsi_overbought': 75,
                'rsi_oversold': 25,
                'short_bias': 0.75,
                'trend_confirmation_period': 1
            },
            # 组合3：激进型（高收益）
            {
                'signal_strength_threshold': 18,
                'base_stoploss_pct': 0.06,
                'base_takeprofit_pct': 0.08,
                'strength_to_position_power': 1.8,
                'momentum_threshold_long': 0.003,
                'momentum_threshold_short': -0.003,
                'rsi_overbought': 70,
                'rsi_oversold': 30,
                'short_bias': 0.80,
                'trend_confirmation_period': 1
            }
        ]
    
    def get_test_combinations(self, method='priority'):
        """获取测试组合"""
        if method == 'priority':
            return self.priority_combinations
        elif method == 'grid':
            # 生成所有组合（慎用，组合数太多）
            keys = self.param_ranges.keys()
            values = self.param_ranges.values()
            all_combinations = []
            for combination in itertools.product(*values):
                all_combinations.append(dict(zip(keys, combination)))
            return all_combinations
        else:
            return self.priority_combinations


# ==================== 回测引擎 ====================
class BacktestTuner:
    """参数调优回测引擎"""
    
    def __init__(self, df):
        self.df = df.copy()
        self.results = []
        
    def run_backtest(self, params):
        """运行单次回测"""
        # 合并参数
        all_params = {**params, **ParameterGrid().base_params}
        
        # 信号生成
        df_test = self.df.copy()
        df_test['signal'] = 'hold'
        df_test['signal_strength'] = 0.0
        df_test['position_size'] = 0.0
        
        for i in range(100, len(df_test)):
            row = df_test.iloc[i]
            
            # 信号条件
            long_condition = (
                row['momentum'] > all_params['momentum_threshold_long'] and
                row['volume_ratio'] > all_params['min_volume_ratio'] and
                row['rsi'] > 30 and row['rsi'] < all_params['rsi_overbought'] and
                row['atr_pct'] < all_params['max_atr_pct']
            )
            
            short_condition = (
                row['momentum'] < all_params['momentum_threshold_short'] and
                row['volume_ratio'] > all_params['min_volume_ratio'] and
                row['rsi'] > all_params['rsi_oversold'] and row['rsi'] < 75 and
                row['atr_pct'] < all_params['max_atr_pct']
            )
            
            # 做空侧重随机过滤
            np.random.seed(i)
            if long_condition and np.random.random() > all_params['short_bias']:
                df_test.at[df_test.index[i], 'signal'] = 'long'
                strength = 50.0
                strength += min(20, max(0, row['momentum'] / 0.01 * 100))
                strength += min(10, max(0, (row['volume_ratio'] - 1) * 50))
                strength += min(15, max(0, (70 - row['rsi']) / 40 * 100))
                strength = min(100, max(0, strength))
                df_test.at[df_test.index[i], 'signal_strength'] = strength
                
            elif short_condition and np.random.random() <= all_params['short_bias']:
                df_test.at[df_test.index[i], 'signal'] = 'short'
                strength = 50.0
                strength += min(20, max(0, abs(row['momentum']) / 0.01 * 100))
                strength += min(10, max(0, (row['volume_ratio'] - 1) * 50))
                strength += min(15, max(0, (row['rsi'] - 30) / 40 * 100))
                strength = min(100, max(0, strength))
                df_test.at[df_test.index[i], 'signal_strength'] = strength
            
            # 动态仓位
            if df_test.at[df_test.index[i], 'signal'] != 'hold':
                strength = df_test.at[df_test.index[i], 'signal_strength']
                strength_ratio = strength / 100
                strength_multiplier = 0.3 + strength_ratio ** all_params['strength_to_position_power'] * 1.7
                atr_multiplier = max(0.5, min(1.5, 0.03 / max(0.01, row['atr_pct'])))
                
                position_size = all_params['base_position_size_pct'] * strength_multiplier * atr_multiplier
                position_size = max(all_params['min_position_size_pct'], 
                                  min(all_params['max_position_size_pct'], position_size))
                df_test.at[df_test.index[i], 'position_size'] = position_size
        
        # 回测模拟
        initial_capital = 10000.0
        capital = initial_capital
        position = 0.0
        position_entry_price = 0.0
        position_type = None
        
        trades = []
        equity_curve = []
        
        for i in range(100, len(df_test)):
            row = df_test.iloc[i]
            price = row['close']
            
            # 检查止损止盈
            if position != 0 and position_entry_price > 0:
                if position_type == 'long':
                    stop_loss = position_entry_price * (1 - all_params['base_stoploss_pct'])
                    take_profit = position_entry_price * (1 + all_params['base_takeprofit_pct'])
                    
                    if price <= stop_loss:
                        revenue = position * price * (1 - all_params['fee_rate'])
                        pnl = (price - position_entry_price) / position_entry_price
                        trades.append({'pnl': pnl, 'reason': '止损'})
                        capital += revenue
                        position = 0
                        position_type = None
                        position_entry_price = 0
                        
                    elif price >= take_profit:
                        revenue = position * price * (1 - all_params['fee_rate'])
                        pnl = (price - position_entry_price) / position_entry_price
                        trades.append({'pnl': pnl, 'reason': '止盈'})
                        capital += revenue
                        position = 0
                        position_type = None
                        position_entry_price = 0
                else:  # short
                    stop_loss = position_entry_price * (1 + all_params['base_stoploss_pct'])
                    take_profit = position_entry_price * (1 - all_params['base_takeprofit_pct'])
                    
                    if price >= stop_loss:
                        revenue = position * price * (1 - all_params['fee_rate'])
                        pnl = (position_entry_price - price) / position_entry_price
                        trades.append({'pnl': pnl, 'reason': '止损'})
                        capital += revenue
                        position = 0
                        position_type = None
                        position_entry_price = 0
                        
                    elif price <= take_profit:
                        revenue = position * price * (1 - all_params['fee_rate'])
                        pnl = (position_entry_price - price) / position_entry_price
                        trades.append({'pnl': pnl, 'reason': '止盈'})
                        capital += revenue
                        position = 0
                        position_type = None
                        position_entry_price = 0
            
            # 开仓（满足强度阈值）
            if position == 0 and row['signal'] != 'hold' and row['signal_strength'] >= all_params['signal_strength_threshold']:
                position_size_pct = row['position_size']
                position_value = capital * position_size_pct
                amount = position_value / price
                
                capital -= position_value
                position = amount
                position_type = row['signal']
                position_entry_price = price
        
        # 计算绩效
        final_capital = capital + (position * df_test.iloc[-1]['close'] if position != 0 else 0)
        total_return_pct = (final_capital - initial_capital) / initial_capital * 100
        
        # 交易统计
        close_trades = trades
        total_trades = len(close_trades)
        winning_trades = len([t for t in close_trades if t.get('pnl', 0) > 0])
        losing_trades = total_trades - winning_trades
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        profits = [t.get('pnl', 0) for t in close_trades if t.get('pnl', 0) > 0]
        losses = [abs(t.get('pnl', 0)) for t in close_trades if t.get('pnl', 0) < 0]
        avg_profit = np.mean(profits) * 100 if profits else 0
        avg_loss = np.mean(losses) * 100 if losses else 0
        profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
        
        return {
            'total_return_pct': total_return_pct,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'final_capital': final_capital,
            'params': all_params
        }
    
    def evaluate_combination(self, params):
        """评估参数组合"""
        try:
            result = self.run_backtest(params)
            
            # 综合评分（越高越好）
            # 权重：收益率40%，胜率20%，盈亏比20%，交易次数10%，风险控制10%
            score = 0
            
            # 收益率评分
            return_score = min(100, max(0, result['total_return_pct'] * 5))  # 20%收益=100分
            score += return_score * 0.4
            
            # 胜率评分
            win_rate_score = min(100, result['win_rate'] * 2)  # 50%胜率=100分
            score += win_rate_score * 0.2
            
            # 盈亏比评分
            pl_ratio_score = min(100, result['profit_loss_ratio'] * 50)  # 2:1=100分
            score += pl_ratio_score * 0.2
            
            # 交易次数评分（适度活跃）
            trade_count_score = min(100, max(0, (result['total_trades'] - 10) * 2))  # 60次=100分
            score += trade_count_score * 0.1
            
            # 风险控制评分（平均亏损越小越好）
            risk_score = max(0, 100 - result['avg_loss'] * 10)  # 亏损5%=50分
            score += risk_score * 0.1
            
            result['score'] = score
            return result
            
        except Exception as e:
            print(f"⚠️  参数组合测试失败: {e}")
            return None


# ==================== 执行调优 ====================
print("\n🔬 开始参数调优...")

# 初始化
grid = ParameterGrid()
tuner = BacktestTuner(df)

# 测试优先组合
print(f"测试{len(grid.priority_combinations)}个优先参数组合...")
for idx, params in enumerate(grid.priority_combinations, 1):
    print(f"  组合{idx}: {params['signal_strength_threshold']}分阈值, {params['base_stoploss_pct']*100:.0f}%止损, {params['base_takeprofit_pct']*100:.0f}%止盈...", end='')
    result = tuner.evaluate_combination(params)
    if result:
        tuner.results.append(result)
        print(f" 评分:{result['score']:.1f}, 收益:{result['total_return_pct']:.2f}%")
    else:
        print(" 失败")

# 排序结果
if tuner.results:
    tuner.results.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"\n✅ 参数调优完成，最佳{min(3, len(tuner.results))}个组合:")
    print("-" * 70)
    
    for idx, result in enumerate(tuner.results[:3], 1):
        params = result['params']
        print(f"\n🥇 第{idx}名 (评分: {result['score']:.1f}):")
        print(f"   收益率: {result['total_return_pct']:.2f}% | 胜率: {result['win_rate']:.1f}% | 盈亏比: {result['profit_loss_ratio']:.2f}:1")
        print(f"   交易次数: {result['total_trades']} | 平均盈利: {result['avg_profit']:.2f}% | 平均亏损: {result['avg_loss']:.2f}%")
        print(f"   关键参数:")
        print(f"     - 信号强度阈值: {params['signal_strength_threshold']}分")
        print(f"     - 止损: {params['base_stoploss_pct']*100:.0f}%, 止盈: {params['base_takeprofit_pct']*100:.0f}%")
        print(f"     - 动态仓位指数: {params['strength_to_position_power']}")
        print(f"     - 动量阈值: 做多{params['momentum_threshold_long']*100:.1f}%, 做空{params['momentum_threshold_short']*100:.1f}%")
        print(f"     - RSI过滤: {params['rsi_overbought']}/{params['rsi_oversold']}")
        print(f"     - 做空侧重: {params['short_bias']*100:.0f}%")

# ==================== 生成配置文件 ====================
print("\n📝 生成优化配置文件...")

if tuner.results:
    best_result = tuner.results[0]
    best_params = best_result['params']
    
    config_content = f"""[OKX]
api_key = 1d9832a1-030e-49a9-90a7-29697d9c4980
api_secret = 34A04573377BFBE85F2CE7F204AD4AC3
api_password = Lqc1234567890@

[Trading]
symbol = ETH-USDT-SWAP
leverage = 10
margin_mode = cross
base_position_size_pct = {best_params['base_position_size_pct']}
max_position_size_pct = {best_params['max_position_size_pct']}
min_position_size_pct = {best_params['min_position_size_pct']}
atr_position_adjust = true
max_daily_trades = 30
max_daily_loss_pct = 0.25
max_total_loss_pct = 0.40
cooling_period_minutes = 2

[Strategy]
timeframe = 5m
momentum_period = 5
momentum_threshold_long = {best_params['momentum_threshold_long']}
momentum_threshold_short = {best_params['momentum_threshold_short']}
rsi_period = {best_params['rsi_period']}
rsi_overbought = {best_params['rsi_overbought']}
rsi_oversold = {best_params['rsi_oversold']}
short_bias = {best_params['short_bias']}
min_volume_ratio = {best_params['min_volume_ratio']}
max_atr_pct = {best_params['max_atr_pct']}
trend_confirmation_period = {best_params['trend_confirmation_period']}

[Risk]
base_stoploss_pct = {best_params['base_stoploss_pct']}
base_takeprofit_pct = {best_params['base_takeprofit_pct']}
atr_stoploss_multiplier = 1.5
atr_takeprofit_multiplier = 2.0
trailing_stop_pct = 0.03

[Optimization]
# 调优结果 (评分: {best_result['score']:.1f}, 收益: {best_result['total_return_pct']:.2f}%)
signal_strength_threshold = {best_params['signal_strength_threshold']}
signal_strength_weights = {{"momentum": 0.15, "volume": 0.10, "rsi": 0.15, "trend": 0.20, "bb": 0.10, "volatility": 0.10, "multi_timeframe": 0.10, "sentiment": 0.10}}
position_size_by_strength = true
strength_to_position_power = {best_params['strength_to_position_power']}
multi_timeframe_confirmation = true
higher_timeframe = 1h
higher_timeframe_weight = 0.3
stop_loss_volatility_adjust = true
stop_loss_trend_adjust = true
volatility_stop_multiplier = 2.0
trend_stop_multiplier = 1.5
ml_signal_scoring = false
ml_model_path = 

[System]
check_interval = 60
enable_trading = true
testnet = true
enable_logging = true
cache_indicators = false
vps_location = HongKong
td_mode = cross
use_simple_orders = true
"""
    
    config_filename = f"config_optimized_tuned_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ini"
    with open(config_filename, 'w') as f:
        f.write(config_content)
    
    print(f"✅ 配置文件已生成: {config_filename}")
    print(f"   预测性能: 收益率{best_result['total_return_pct']:.2f}%, 胜率{best_result['win_rate']:.1f}%, 盈亏比{best_result['profit_loss_ratio']:.2f}:1")

print("\n" + "=" * 70)
print("💡 参数调优建议:")
print("-" * 70)
print("1. 测试最佳参数组合的90天回测，验证稳定性")
print("2. 关注风险指标: 最大回撤 < 25%, 夏普比率 > 0.5")
print("3. 实盘前进行至少30天模拟交易验证")
print("4. 监控交易频率，避免过度交易")
print("=" * 70)