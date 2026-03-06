#!/usr/bin/env python3
"""
快速检查持仓和余额
"""

import ccxt
import configparser

config = configparser.ConfigParser()
config.read('config.ini')

api_key = config.get('OKX', 'api_key', fallback='')
api_secret = config.get('OKX', 'api_secret', fallback='')
api_password = config.get('OKX', 'api_password', fallback='')
symbol = config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')
testnet = config.getboolean('System', 'testnet', fallback=True)

exchange = ccxt.okx({
    'apiKey': api_key,
    'secret': api_secret,
    'password': api_password,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap',
        'sandbox': testnet,
    }
})

print("🔍 检查持仓和余额")
print("=" * 50)

try:
    # 加载市场
    exchange.load_markets()
    
    # 检查余额
    balance = exchange.fetch_balance()
    usdt_total = balance['USDT']['total'] if 'USDT' in balance else 0
    usdt_free = balance['USDT']['free'] if 'USDT' in balance else 0
    print(f"💰 USDT总余额: {usdt_total}")
    print(f"   USDT可用余额: {usdt_free}")
    
    # 检查持仓
    positions = exchange.fetch_positions([symbol])
    open_positions = [p for p in positions if float(p.get('contracts', 0)) != 0]
    
    print(f"\n📊 持仓数量: {len(open_positions)}")
    for pos in open_positions:
        print(f"   合约: {pos['symbol']}")
        print(f"   方向: {pos['side']}")
        print(f"   数量: {pos.get('contracts', 0)}")
        print(f"   持仓价值: {pos.get('notional', 0)} USDT")
        print(f"   开仓均价: {pos.get('entryPrice', 0)}")
        print(f"   未实现盈亏: {pos.get('unrealizedPnl', 0)}")
        print()
        
    if not open_positions:
        print("   ✅ 无未平仓持仓")
        
except Exception as e:
    print(f"❌ 检查失败: {e}")
    import traceback
    traceback.print_exc()