#!/usr/bin/env python3
"""
测试新的配置参数
"""

import ccxt
import configparser

def test_order_with_new_config():
    print("🔧 测试新配置参数下单")
    
    # 加载配置
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    api_key = config.get('OKX', 'api_key', fallback='')
    api_secret = config.get('OKX', 'api_secret', fallback='')
    api_password = config.get('OKX', 'api_password', fallback='')
    symbol = config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')
    margin_mode = config.get('Trading', 'margin_mode', fallback='cross')
    td_mode = config.get('System', 'td_mode', fallback='cross')
    testnet = config.getboolean('System', 'testnet', fallback=True)
    use_simple_orders = config.getboolean('System', 'use_simple_orders', fallback=True)
    
    print(f"📋 配置:")
    print(f"   td_mode: {td_mode}")
    print(f"   margin_mode: {margin_mode}")
    print(f"   use_simple_orders: {use_simple_orders}")
    print(f"   testnet: {testnet}")
    
    # 初始化交易所
    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': api_secret,
        'password': api_password,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
            'sandbox': testnet,
            'defaultMarginMode': margin_mode,
        }
    })
    
    try:
        # 获取账户信息
        print("\n🔍 获取账户信息...")
        balance = exchange.fetch_balance()
        usdt_balance = balance['USDT']['total'] if 'USDT' in balance else 0
        print(f"   USDT余额: {usdt_balance}")
        
        # 获取市场信息
        market = exchange.market(symbol)
        min_amount = market['limits']['amount']['min']
        print(f"   最小下单数量: {min_amount}")
        
        # 获取当前价格
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"   当前价格: {current_price}")
        
        # 尝试下单
        print(f"\n🧪 测试下单 (tdMode={td_mode})...")
        try:
            order = exchange.create_order(
                symbol=symbol,
                type='market',
                side='buy',
                amount=min_amount,
                params={'tdMode': td_mode}
            )
            print(f"   ✅ 下单成功! 订单ID: {order.get('id', 'N/A')}")
            print(f"   状态: {order.get('status', 'N/A')}")
            
            # 如果是开放订单，尝试取消
            if order.get('status') in ['open', 'new']:
                exchange.cancel_order(order['id'], symbol)
                print("   ✅ 订单已取消")
            else:
                print("   ⚠️  市价单可能已成交")
                
        except Exception as e:
            print(f"   ❌ 下单失败: {e}")
            
            # 尝试其他模式
            print(f"\n🔧 尝试其他tdMode值...")
            for test_mode in ['cross', 'isolated', 'cash', 'net_mode']:
                try:
                    print(f"   测试 tdMode={test_mode}...")
                    order2 = exchange.create_order(
                        symbol=symbol,
                        type='market',
                        side='buy',
                        amount=min_amount,
                        params={'tdMode': test_mode}
                    )
                    print(f"   ✅ tdMode={test_mode} 成功!")
                    break
                except Exception as e2:
                    print(f"   ❌ tdMode={test_mode} 失败: {e2}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    test_order_with_new_config()