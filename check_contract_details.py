#!/usr/bin/env python3
"""
检查合约详细信息
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

print("🔍 检查合约详细信息")
print("=" * 50)

try:
    # 加载市场
    exchange.load_markets()
    
    # 获取市场信息
    market = exchange.market(symbol)
    print(f"交易对: {symbol}")
    print(f"规范化symbol: {market['symbol']}")
    print(f"标的物: {market['base']}/{market['quote']}")
    print(f"合约类型: {market['type']}")
    print(f"合约乘数: {market.get('contractSize', 'N/A')}")
    print(f"最小下单数量: {market['limits']['amount']['min']}")
    print(f"数量步长: {market['precision']['amount']}")
    print(f"价格精度: {market['precision']['price']}")
    print()
    
    # 获取当前价格
    ticker = exchange.fetch_ticker(symbol)
    current_price = ticker['last']
    print(f"当前价格: ${current_price}")
    
    # 检查持仓
    positions = exchange.fetch_positions([symbol])
    print(f"\n持仓数量: {len(positions)}")
    
    for i, pos in enumerate(positions):
        print(f"\n持仓 {i+1}:")
        for key, value in pos.items():
            if key not in ['info', 'timestamp', 'datetime'] and value is not None:
                print(f"  {key}: {value}")
    
    # 计算实际价值
    if positions:
        pos = positions[0]
        contracts = float(pos.get('contracts', 0))
        notional = float(pos.get('notional', 0))
        entry_price = float(pos.get('entryPrice', 0))
        
        print(f"\n📊 持仓价值分析:")
        print(f"  合约数量: {contracts}")
        print(f"  持仓价值(notional): ${notional}")
        print(f"  开仓均价: ${entry_price}")
        
        # 计算理论价值
        contract_size = market.get('contractSize', 1)
        print(f"  合约乘数: {contract_size}")
        
        if contract_size != 1:
            actual_eth = contracts * contract_size
            print(f"  实际ETH数量: {actual_eth} ETH")
            print(f"  理论价值: ${actual_eth * current_price:.2f}")
            print(f"  理论开仓价值: ${actual_eth * entry_price:.2f}")
        
except Exception as e:
    print(f"❌ 检查失败: {e}")
    import traceback
    traceback.print_exc()