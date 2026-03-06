#!/usr/bin/env python3
"""
深度调试API参数，找出正确的下单方式
"""

import ccxt
import os
import configparser
import json

def debug_api():
    """深度调试API"""
    print("🔍 深度调试OKX API参数")
    
    # 加载配置
    config = configparser.ConfigParser()
    config.read('config_clean.ini')
    
    api_key = config.get('OKX', 'api_key', fallback='')
    api_secret = config.get('OKX', 'api_secret', fallback='')
    api_password = config.get('OKX', 'api_password', fallback='')
    symbol = config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')
    testnet = config.getboolean('System', 'testnet', fallback=True)
    
    print(f"📋 配置:")
    print(f"   交易对: {symbol}")
    print(f"   模拟环境: {testnet}")
    print(f"   API密钥: {api_key[:8]}...")
    
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
    
    try:
        # 1. 获取账户详细信息
        print("\n1️⃣ 获取账户详细信息...")
        try:
            account_config = exchange.private_get_account_config()
            print(f"   账户配置: {json.dumps(account_config.get('data', [{}])[0], indent=2)}")
        except Exception as e:
            print(f"   获取账户配置失败: {e}")
        
        # 2. 检查模拟账户的可用性
        print("\n2️⃣ 检查模拟账户可用性...")
        try:
            # 获取模拟账户特定信息
            demo_account = exchange.private_get_account_demo_info()
            print(f"   模拟账户信息: {json.dumps(demo_account.get('data', {}), indent=2)}")
        except Exception as e:
            print(f"   获取模拟账户信息失败（可能不是模拟账户）: {e}")
        
        # 3. 获取交易规则
        print("\n3️⃣ 获取交易规则...")
        try:
            instruments = exchange.public_get_public_instruments({
                'instType': 'SWAP',
                'instId': symbol
            })
            print(f"   合约信息: {json.dumps(instruments.get('data', [{}])[0], indent=2)}")
        except Exception as e:
            print(f"   获取合约信息失败: {e}")
        
        # 4. 获取当前持仓
        print("\n4️⃣ 获取当前持仓...")
        try:
            positions = exchange.fetch_positions([symbol])
            print(f"   持仓数量: {len(positions)}")
            for i, pos in enumerate(positions):
                if pos['symbol'] == symbol:
                    print(f"   持仓{i+1}: {json.dumps({k: v for k, v in pos.items() if k in ['symbol', 'contracts', 'entryPrice', 'markPrice', 'side', 'unrealizedPnl']}, indent=2)}")
        except Exception as e:
            print(f"   获取持仓失败: {e}")
        
        # 5. 分析手动下单的可能参数
        print("\n5️⃣ 分析手动下单参数...")
        print("   手动下单成功 → 我们需要模拟手动下单的参数")
        
        # 猜测手动下单可能使用的参数
        print("   猜测参数组合:")
        print("   A. 使用net_mode（账户显示是net_mode）")
        print("   B. 可能不需要tdMode参数")
        print("   C. 可能需要特殊的下单接口")
        
        # 6. 测试不同下单方式
        print("\n6️⃣ 测试不同下单方式...")
        
        # 获取最小下单数量
        market = exchange.market(symbol)
        min_amount = market['limits']['amount']['min']
        print(f"   最小下单数量: {min_amount}")
        
        # 获取当前价格
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"   当前价格: {current_price}")
        
        # 测试方案列表
        test_cases = [
            {
                'name': '方案1: 不使用tdMode',
                'params': {}
            },
            {
                'name': '方案2: tdMode=net_mode',
                'params': {'tdMode': 'net_mode'}
            },
            {
                'name': '方案3: 使用posMode',
                'params': {'posMode': 'net_mode'}
            },
            {
                'name': '方案4: 简单下单，无参数',
                'params': None  # 表示不带params
            },
            {
                'name': '方案5: 使用ccxt默认',
                'params': {'tdMode': 'cross'}  # ccxt默认
            },
        ]
        
        for test_case in test_cases:
            print(f"\n   🧪 {test_case['name']}")
            try:
                order_data = {
                    'symbol': symbol,
                    'type': 'market',
                    'side': 'buy',
                    'amount': min_amount,
                }
                
                if test_case['params'] is not None:
                    order_data['params'] = test_case['params']
                
                print(f"     下单数据: {order_data}")
                
                # 检查是否有足够余额
                balance = exchange.fetch_balance()
                usdt_balance = balance['total'].get('USDT', 0)
                order_value = min_amount * current_price
                
                if usdt_balance < order_value:
                    print(f"     ⚠️  余额不足: {usdt_balance:.2f} USDT < {order_value:.2f} USDT")
                    continue
                
                # 尝试下单
                order = exchange.create_order(**order_data)
                print(f"     ✅ 下单成功!")
                print(f"       订单ID: {order.get('id', 'N/A')}")
                print(f"       状态: {order.get('status', 'N/A')}")
                
                # 如果是限价单，取消它
                if order.get('status') in ['open', 'new']:
                    exchange.cancel_order(order['id'], symbol)
                    print(f"     ✅ 订单已取消")
                
                # 如果是市价单，检查是否成交
                elif order.get('status') == 'closed' or order.get('filled', 0) > 0:
                    print(f"     ⚠️  市价单可能已成交")
                    
                    # 检查持仓
                    positions = exchange.fetch_positions([symbol])
                    for pos in positions:
                        if pos['symbol'] == symbol and abs(float(pos.get('contracts', 0))) > 0.001:
                            print(f"     📊 检测到持仓，尝试平仓...")
                            side = 'sell' if float(pos['contracts']) > 0 else 'buy'
                            close_order = exchange.create_order(
                                symbol=symbol,
                                type='market',
                                side=side,
                                amount=abs(float(pos['contracts']))
                            )
                            print(f"     ✅ 平仓成功: {close_order.get('id', 'N/A')}")
                
                # 找到正确方法，结束测试
                print(f"\n🎉 找到正确的下单方式: {test_case['name']}")
                print(f"   正确参数: {test_case['params']}")
                return test_case['params']
                
            except Exception as e:
                error_str = str(e)
                print(f"     ❌ 失败: {error_str[:100]}...")
                
                # 分析错误
                if '51010' in error_str:
                    print(f"     错误51010: 账户模式不匹配")
                elif '51000' in error_str:
                    print(f"     错误51000: 参数错误")
                elif '50101' in error_str:
                    print(f"     错误50101: API环境不匹配")
                else:
                    print(f"     其他错误")
        
        print("\n❌ 所有方案都失败了")
        print("   建议:")
        print("   1. 检查手动下单时的具体参数")
        print("   2. 查看OKX API文档的模拟账户部分")
        print("   3. 尝试使用不同的API端点")
        
        # 7. 尝试使用原始API调用
        print("\n7️⃣ 尝试原始API调用...")
        try:
            # 获取ccxt使用的实际URL和参数
            print("   查看ccxt内部调用...")
            exchange.verbose = True  # 启用详细日志
            print("   （需要修改代码查看详细日志）")
        except Exception as e:
            print(f"   原始API调用失败: {e}")
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")

if __name__ == "__main__":
    debug_api()