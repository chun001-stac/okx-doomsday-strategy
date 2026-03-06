#!/usr/bin/env python3
"""
修改策略文件以集成ML数据收集器
"""

import re

# 读取文件
with open('okx_doomsday_optimized_v2_ml_integrated.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 在import部分添加ml_data_collector
import_pattern = r'import warnings\nwarnings\.filterwarnings\(\'ignore\'\)'
import_replacement = '''import warnings
import ml_data_collector
warnings.filterwarnings('ignore')'''

if 'import ml_data_collector' not in content:
    content = re.sub(import_pattern, import_replacement, content, flags=re.DOTALL)

# 2. 在FixedTradingSystem.__init__中添加MLDataCollector初始化
init_pattern = r'(self\.signal_generator = OptimizedSignalGenerator\(config, self\.exchange\)\s*\n\s*)'
init_replacement = '''self.signal_generator = OptimizedSignalGenerator(config, self.exchange)
        
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
        '''

if 'self.ml_collector' not in content:
    content = re.sub(init_pattern, init_replacement, content, flags=re.DOTALL)

# 3. 在close_position方法中添加交易数据收集
close_position_pattern = r'(def close_position\(self, reason: str = \'signal\'\) -> bool:)'
close_position_replacement = '''def close_position(self, reason: str = 'signal') -> bool:
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
                self.logger.error(f"收集交易数据失败: {e}")'''

if 'self.ml_collector' not in content or 'collect_trade_data' not in content:
    # 需要找到close_position方法并替换其开始部分
    # 先查找方法定义
    match = re.search(r'def close_position\(self, reason: str = \'signal\'\) -> bool:.*?(?=\n    def|\nclass|\Z)', content, re.DOTALL)
    if match:
        original_method = match.group(0)
        # 在方法开头添加收集代码
        new_method = original_method.replace(
            'def close_position(self, reason: str = \'signal\') -> bool:',
            close_position_replacement
        )
        content = content.replace(original_method, new_method)

# 4. 在calculate_signals方法中添加信号数据收集
# 这需要在OptimizedSignalGenerator中修改，比较复杂，暂时跳过

# 保存修改后的文件
with open('okx_doomsday_optimized_v2_ml_integrated.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ ML集成修改完成")