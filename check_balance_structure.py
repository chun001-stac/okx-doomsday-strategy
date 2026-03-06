#!/usr/bin/env python3
"""
检查余额结构
"""

import ccxt
import configparser
import json

config = configparser.ConfigParser()
config.read('config.ini')

api_key = config.get('OKX', 'api_key', fallback='')
api_secret = config.get('OKX', 'api_secret', fallback='')
api_password = config.get('OKX', 'api_password', fallback='')
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

print("🔍 检查余额结构")
print("=" * 50)

try:
    # 获取余额
    balance = exchange.fetch_balance()
    
    print("完整余额结构:")
    print(json.dumps(balance, indent=2, default=str))
    
    print("\n💰 USDT余额详情:")
    if 'USDT' in balance:
        print(f"  total: {balance['USDT'].get('total', 'N/A')}")
        print(f"  free: {balance['USDT'].get('free', 'N/A')}")
        print(f"  used: {balance['USDT'].get('used', 'N/A')}")
    
    print("\n💡 总余额结构:")
    if 'total' in balance:
        print(f"  total dict keys: {list(balance['total'].keys())}")
        if 'USDT' in balance['total']:
            print(f"  total['USDT']: {balance['total']['USDT']}")
    
    # 测试两种获取方式
    print("\n🧪 测试余额获取方式:")
    
    # 方式1: balance['USDT']['total']
    usdt_total_1 = balance['USDT']['total'] if 'USDT' in balance else 0
    print(f"  1. balance['USDT']['total']: {usdt_total_1}")
    
    # 方式2: balance['total'].get('USDT', 0)
    usdt_total_2 = balance['total'].get('USDT', 0) if 'total' in balance else 0
    print(f"  2. balance['total'].get('USDT', 0): {usdt_total_2}")
    
    # 计算10%仓位
    current_price = 2560.0  # 近似值
    position_value_1 = usdt_total_1 * 0.10
    position_value_2 = usdt_total_2 * 0.10
    
    print(f"\n📊 10%仓位计算:")
    print(f"  使用方式1: {position_value_1:.2f} USDT")
    print(f"  使用方式2: {position_value_2:.2f} USDT")
    
    # 转换为合约数量
    contract_size = 0.1  # ETH合约乘数
    contracts_1 = position_value_1 / current_price / contract_size
    contracts_2 = position_value_2 / current_price / contract_size
    
    print(f"\n📈 合约数量计算:")
    print(f"  使用方式1: {contracts_1:.4f} 合约 ({contracts_1 * contract_size:.4f} ETH)")
    print(f"  使用方式2: {contracts_2:.4f} 合约 ({contracts_2 * contract_size:.4f} ETH)")
    
except Exception as e:
    print(f"❌ 检查失败: {e}")
    import json
    import traceback
    traceback.print_exc()