#!/usr/bin/env python3
"""
测试仓位计算
"""

import ccxt
import configparser

config = configparser.ConfigParser()
config.read('config.ini')

api_key = config.get('OKX', 'api_key', fallback='')
api_secret = config.get('OKX', 'api_secret', fallback='')
api_password = config.get('OKX', 'api_password', fallback='')
symbol = config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')
base_position_size_pct = float(config.get('Trading', 'base_position_size_pct', fallback='0.10'))
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

print("🧪 测试仓位计算")
print("=" * 50)

try:
    # 加载市场
    exchange.load_markets()
    market = exchange.market(symbol)
    
    # 获取余额
    balance = exchange.fetch_balance()
    usdt_total_1 = balance['total'].get('USDT', 0) if 'total' in balance else 0
    usdt_total_2 = balance['USDT']['total'] if 'USDT' in balance else 0
    
    print(f"余额获取方式对比:")
    print(f"  balance['total'].get('USDT', 0) = {usdt_total_1}")
    print(f"  balance['USDT']['total'] = {usdt_total_2}")
    
    # 使用第一种方式（标准ccxt方式）
    usdt_balance = usdt_total_1
    position_value = usdt_balance * base_position_size_pct
    print(f"\n仓位计算:")
    print(f"  总余额: {usdt_balance} USDT")
    print(f"  仓位比例: {base_position_size_pct*100:.1f}%")
    print(f"  仓位价值: {position_value:.2f} USDT")
    
    # 获取当前价格
    ticker = exchange.fetch_ticker(symbol)
    current_price = ticker['last']
    print(f"  当前价格: ${current_price}")
    
    # 合约信息
    contract_size = market.get('contractSize', 0.1)
    print(f"  合约乘数: {contract_size}")
    
    # 计算ETH数量
    eth_amount = position_value / current_price
    print(f"  ETH数量: {eth_amount:.6f} ETH")
    
    # 计算合约数量
    contract_amount = eth_amount / contract_size
    print(f"  合约数量: {contract_amount:.6f} 合约")
    
    # 最小下单数量
    min_amount = market['limits']['amount']['min']
    print(f"  最小下单数量: {min_amount} 合约")
    
    # 调整到最小数量
    if contract_amount < min_amount:
        contract_amount = min_amount
        print(f"  调整后合约数量: {contract_amount} 合约")
    
    # 实际ETH价值
    actual_eth = contract_amount * contract_size
    actual_value = actual_eth * current_price
    print(f"\n实际开仓:")
    print(f"  合约数量: {contract_amount:.4f}")
    print(f"  ETH数量: {actual_eth:.6f} ETH")
    print(f"  价值: ${actual_value:.2f} USDT")
    print(f"  占比: {(actual_value / usdt_balance * 100):.2f}%")
    
    # 对比当前持仓
    positions = exchange.fetch_positions([symbol])
    for pos in positions:
        contracts = float(pos.get('contracts', 0))
        if abs(contracts) > 0.001:
            print(f"\n当前持仓对比:")
            print(f"  实际持仓合约: {contracts}")
            print(f"  计算应持仓: {contract_amount:.4f}")
            print(f"  差异: {abs(contracts - contract_amount):.4f} 合约")
            
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()