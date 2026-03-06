#!/usr/bin/env python3
import ccxt
import configparser
import os

# 加载配置文件
config = configparser.ConfigParser()
config.read('config.ini')

api_key = config['OKX']['api_key']
api_secret = config['OKX']['api_secret']
api_password = config['OKX']['api_password']

# 创建交易所连接
exchange = ccxt.okx({
    'apiKey': api_key,
    'secret': api_secret,
    'password': api_password,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap',
    },
    'testnet': True,
})

try:
    # 加载市场数据
    exchange.load_markets()
    
    print("可用的永续合约交易对：")
    print("-" * 50)
    
    # 只显示USDT结算的永续合约
    usdt_swap_symbols = []
    for symbol, market in exchange.markets.items():
        if market['swap'] and market['settle'] == 'USDT' and market['type'] == 'swap':
            usdt_swap_symbols.append(symbol)
    
    # 排序并显示
    usdt_swap_symbols.sort()
    for i, symbol in enumerate(usdt_swap_symbols, 1):
        print(f"{i:3d}. {symbol}")
    
    print(f"\n总计: {len(usdt_swap_symbols)} 个USDT永续合约")
    
    # 检查特定交易对
    symbols_to_check = ['ETH-USDT-SWAP', 'BTC-USDT-SWAP', 'OKB-USDT-SWAP', 'SOL-USDT-SWAP', 'OKB/USDT:USDT', 'SOL/USDT:USDT']
    print(f"\n检查特定交易对：")
    for symbol in symbols_to_check:
        if symbol in exchange.markets:
            print(f"  ✓ {symbol}: 可用")
        else:
            print(f"  ✗ {symbol}: 不可用")
            
except Exception as e:
    print(f"错误: {e}")