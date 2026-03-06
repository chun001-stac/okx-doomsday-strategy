#!/usr/bin/env python3
"""
测试posSide参数
"""

import ccxt
import configparser

def test_posside():
    print("🔧 测试posSide参数")
    
    # 加载配置
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    api_key = config.get('OKX', 'api_key', fallback='')
    api_secret = config.get('OKX', 'api_secret', fallback='')
    api_password = config.get('OKX', 'api_password', fallback='')
    symbol = config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')
    td_mode = config.get('System', 'td_mode', fallback='cross')
    testnet = config.getboolean('System', 'testnet', fallback=True)
    
    # 初始化交易所
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
    
    # 获取市场信息
    market = exchange.market(symbol)
    min_amount = market['limits']['amount']['min']
    print(f"最小下单数量: {min_amount}")
    
    # 获取当前价格
    ticker = exchange.fetch_ticker(symbol)
    current_price = ticker['last']
    print(f"当前价格: {current_price}")
    
    # 测试不同组合
    test_cases = [
        {'tdMode': 'cross', 'posSide': 'long'},
        {'tdMode': 'cross', 'posSide': 'short'},
        {'tdMode': 'isolated', 'posSide': 'long'},
        {'tdMode': 'isolated', 'posSide': 'short'},
        {'tdMode': 'cash', 'posSide': 'long'},
        {'tdMode': 'cash', 'posSide': 'short'},
        {'tdMode': 'cross'},  # 无posSide
        {'tdMode': 'isolated'},  # 无posSide
        {'tdMode': 'cash'},  # 无posSide
    ]
    
    for i, params in enumerate(test_cases):
        print(f"\n测试 {i+1}: params={params}")
        try:
            order = exchange.create_order(
                symbol=symbol,
                type='market',
                side='buy',
                amount=min_amount,
                params=params
            )
            print(f"✅ 成功! 订单ID: {order.get('id', 'N/A')}")
            # 取消订单（如果是限价单）
            if order.get('status') in ['open', 'new']:
                exchange.cancel_order(order['id'], symbol)
                print("订单已取消")
            break
        except Exception as e:
            print(f"❌ 失败: {e}")

if __name__ == "__main__":
    test_posside()