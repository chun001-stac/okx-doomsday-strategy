#!/usr/bin/env python3
"""
测试配置加载
"""

import sys
import os
import configparser

sys.path.append('.')

try:
    from okx_doomsday_optimized import load_config, Config
    print("✅ 模块导入成功")
    
    config = load_config()
    print(f"✅ 配置加载成功")
    print(f"   交易对: {config.symbol}")
    print(f"   杠杆: {config.leverage}")
    print(f"   仓位比例: {config.base_position_size_pct}")
    print(f"   每日最大交易次数: {config.max_daily_trades}")
    print(f"   做多动量阈值: {config.momentum_threshold_long}")
    print(f"   做空动量阈值: {config.momentum_threshold_short}")
    print(f"   做空侧重: {config.short_bias}")
    print(f"   最小成交量比率: {config.min_volume_ratio}")
    print(f"   最大ATR百分比: {config.max_atr_pct}")
    print(f"   测试网模式: {config.testnet}")
    print(f"   启用交易: {config.enable_trading}")
    
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()