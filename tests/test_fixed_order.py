#!/usr/bin/env python3
"""
测试修复版下单功能
"""

import ccxt
import os
import configparser

def test_fixed_order():
    """测试修复版下单"""
    print("🧪 测试修复版下单功能")
    
    # 加载修复配置
    config = configparser.ConfigParser()
    config.read('config_fixed_v2.ini')
    
    api_key = config.get('OKX', 'api_key', fallback='')
    api_secret = config.get('OKX', 'api_secret', fallback='')
    api_password = config.get('OKX', 'api_password', fallback='')
    symbol = config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')
    td_mode = config.get('System', 'td_mode', fallback='cross')
    margin_mode = config.get('Trading', 'margin_mode', fallback='cross')
    testnet = config.getboolean('System', 'testnet', fallback=True)
    
    print(f"📋 修复配置:")
    print(f"   交易模式(td_mode): {td_mode}")
    print(f"   保证金模式: {margin_mode}")
    print(f"   交易对: {symbol}")
    print(f"   模拟环境: {testnet}")
    
    # 初始化交易所（使用修复版配置）
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
        usdt_balance = balance['total'].get('USDT', 0)
        print(f"✅ 连接成功")
        print(f"   账户余额: {usdt_balance:,.2f} USDT")
        
        # 检查账户配置
        try:
            account_config = exchange.private_get_account_config()
            pos_mode = account_config.get('data', [{}])[0].get('posMode', '未知')
            acct_lv = account_config.get('data', [{}])[0].get('acctLv', '未知')
            print(f"   账户级别: {acct_lv}")
            print(f"   仓位模式: {pos_mode}")
        except Exception as e:
            print(f"   获取账户配置失败: {e}")
        
        # 获取市场信息
        print("\n💰 获取市场数据...")
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"   当前价格: {current_price}")
        
        market = exchange.market(symbol)
        min_amount = market['limits']['amount']['min']
        print(f"   最小下单数量: {min_amount}")
        
        # 测试1: 修复版下单（带tdMode参数）
        print(f"\n🧪 测试1: 修复版下单（tdMode={td_mode}）")
        try:
            order_params = {
                'symbol': symbol,
                'type': 'market',
                'side': 'buy',
                'amount': min_amount,
                'params': {
                    'tdMode': td_mode,
                }
            }
            
            print(f"   下单参数: {order_params}")
            
            # 检查交易是否启用
            enable_trading = config.getboolean('System', 'enable_trading', fallback=True)
            if not enable_trading:
                print("⚠️  交易未启用 (enable_trading=false)")
                return
            
            # 尝试下单
            order = exchange.create_order(**order_params)
            print(f"✅ 下单成功!")
            print(f"   订单ID: {order.get('id', 'N/A')}")
            print(f"   状态: {order.get('status', 'N/A')}")
            print(f"   成交数量: {order.get('filled', 'N/A')}")
            
            # 如果是市价单，可能立即成交
            if order.get('status') == 'closed' or order.get('filled') == min_amount:
                print("   ⚠️  市价单可能已成交")
                
                # 检查持仓
                positions = exchange.fetch_positions([symbol])
                open_positions = []
                for pos in positions:
                    if pos['symbol'] == symbol and abs(float(pos.get('contracts', 0))) > 0.001:
                        open_positions.append(pos)
                
                if open_positions:
                    print(f"   📊 当前持仓: {len(open_positions)} 个")
                    
                    # 立即平仓
                    print("   🔄 立即平仓...")
                    for pos in open_positions:
                        side = 'sell' if float(pos['contracts']) > 0 else 'buy'
                        close_order = exchange.create_order(
                            symbol=symbol,
                            type='market',
                            side=side,
                            amount=abs(float(pos['contracts'])),
                            params={'tdMode': td_mode}
                        )
                        print(f"   ✅ 平仓成功: {close_order.get('id', 'N/A')}")
                else:
                    print("   ✅ 无持仓")
            
            # 如果是限价单，取消它
            elif order.get('status') in ['open', 'new']:
                print("\n🔄 取消测试订单...")
                exchange.cancel_order(order['id'], symbol)
                print("✅ 订单已取消")
            
        except Exception as e:
            print(f"❌ 下单失败: {e}")
            
            # 分析错误
            error_str = str(e)
            if '51010' in error_str:
                print("🔍 仍然出现51010错误")
                print("可能原因:")
                print("1. 模拟账户可能完全禁用交易")
                print("2. 需要手动在OKX模拟界面激活")
                print("3. 账户权限问题")
            elif '51000' in error_str:
                print("🔍 tdMode参数可能不正确")
                print("尝试其他tdMode值: cash, isolated, cross")
        
        # 测试2: 不同tdMode值
        print(f"\n🧪 测试2: 尝试不同tdMode值")
        td_modes_to_test = ['cash', 'isolated', 'cross']
        
        for test_td_mode in td_modes_to_test:
            if test_td_mode == td_mode:
                continue  # 已经测试过
            
            print(f"   尝试tdMode={test_td_mode}...")
            try:
                test_order = exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side='buy',
                    amount=min_amount,
                    params={'tdMode': test_td_mode}
                )
                print(f"   ✅ tdMode={test_td_mode} 下单成功!")
                
                # 立即取消或平仓
                if test_order.get('status') in ['open', 'new']:
                    exchange.cancel_order(test_order['id'], symbol)
                    print("   ✅ 订单已取消")
                break  # 成功则停止测试
                
            except Exception as e2:
                print(f"   ❌ tdMode={test_td_mode} 失败: {e2}")
        
        print("\n📋 测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    test_fixed_order()