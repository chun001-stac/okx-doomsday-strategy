#!/usr/bin/env python3
"""
测试修复51010错误
"""

import ccxt
import os
import configparser

def test_fix():
    """测试修复"""
    print("🔧 测试51010错误修复")
    
    # 加载修复配置
    config = configparser.ConfigParser()
    config.read('config_fixed.ini')
    
    api_key = config.get('OKX', 'api_key', fallback='')
    api_secret = config.get('OKX', 'api_secret', fallback='')
    api_password = config.get('OKX', 'api_password', fallback='')
    symbol = config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')
    margin_mode = config.get('Trading', 'margin_mode', fallback='cross')
    testnet = config.getboolean('System', 'testnet', fallback=True)
    
    print(f"📋 使用配置:")
    print(f"   保证金模式: {margin_mode}")
    print(f"   交易对: {symbol}")
    print(f"   模拟环境: {testnet}")
    
    # 初始化交易所
    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': api_secret,
        'password': api_password,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
            'sandbox': testnet,
            'defaultMarginMode': margin_mode,  # 设置保证金模式
        }
    })
    
    try:
        # 获取账户配置
        print("\n🔍 获取账户配置...")
        account_config = exchange.private_get_account_config()
        pos_mode = account_config.get('data', [{}])[0].get('posMode', '未知')
        acct_lv = account_config.get('data', [{}])[0].get('acctLv', '未知')
        print(f"   账户级别: {acct_lv}")
        print(f"   仓位模式: {pos_mode}")
        
        # 设置仓位模式（如果需要）
        if pos_mode != 'net_mode':
            print(f"⚠️  当前仓位模式: {pos_mode}, 尝试设置为net_mode...")
            try:
                exchange.private_post_account_set_position_mode({
                    'posMode': 'net_mode'
                })
                print("✅ 已设置仓位模式为net_mode")
            except Exception as e:
                print(f"❌ 设置仓位模式失败: {e}")
        
        # 测试下单（不带止损止盈）
        print("\n🧪 测试下单（简化版）...")
        
        # 获取当前价格
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"   当前价格: {current_price}")
        
        # 计算最小下单数量
        market = exchange.market(symbol)
        min_amount = market['limits']['amount']['min']
        print(f"   最小下单数量: {min_amount}")
        
        # 测试1: 简单市场单
        print(f"\n   测试1: 市场单 {min_amount} {symbol}")
        try:
            order = exchange.create_order(
                symbol=symbol,
                type='market',
                side='buy',
                amount=min_amount,
                params={}  # 空参数，不带止损止盈
            )
            print(f"   ✅ 下单成功! 订单ID: {order.get('id', 'N/A')}")
            
            # 立即取消（如果是限价单）
            if order.get('status') in ['open', 'new']:
                exchange.cancel_order(order['id'], symbol)
                print("   ✅ 订单已取消")
            else:
                print("   ⚠️  市价单可能已成交")
                
        except Exception as e:
            print(f"   ❌ 下单失败: {e}")
            
            # 检查具体错误
            error_str = str(e)
            if '51010' in error_str:
                print("   🔍 检测到51010错误 - 账户模式问题")
                print("   可能原因:")
                print("   1. 模拟账户不支持交易")
                print("   2. 需要手动激活模拟账户")
                print("   3. 账户权限不足")
                print("   4. 需要特殊参数")
            
            # 尝试不同方式
            print(f"\n   测试2: 使用不同参数...")
            try:
                # 尝试使用不同的保证金模式
                order2 = exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side='buy',
                    amount=min_amount,
                    params={'tdMode': 'cross'}  # 交易模式: cross
                )
                print(f"   ✅ 使用tdMode=cross下单成功!")
            except Exception as e2:
                print(f"   ❌ 方式2失败: {e2}")
                
                # 尝试isolated模式
                print(f"\n   测试3: 使用tdMode=isolated...")
                try:
                    order3 = exchange.create_order(
                        symbol=symbol,
                        type='market',
                        side='buy',
                        amount=min_amount,
                        params={'tdMode': 'isolated'}
                    )
                    print(f"   ✅ 使用tdMode=isolated下单成功!")
                except Exception as e3:
                    print(f"   ❌ 方式3失败: {e3}")
                    
                    # 尝试cash模式
                    print(f"\n   测试4: 使用tdMode=cash...")
                    try:
                        order4 = exchange.create_order(
                            symbol=symbol,
                            type='market',
                            side='buy',
                            amount=min_amount,
                            params={'tdMode': 'cash'}
                        )
                        print(f"   ✅ 使用tdMode=cash下单成功!")
                    except Exception as e4:
                        print(f"   ❌ 方式4失败: {e4}")
        
        # 测试止损止盈订单
        print("\n🧪 测试止损止盈订单...")
        try:
            # 计算止损止盈价格
            stop_loss_price = current_price * 0.95  # -5%
            take_profit_price = current_price * 1.05  # +5%
            
            print(f"   止损价: {stop_loss_price:.2f}")
            print(f"   止盈价: {take_profit_price:.2f}")
            
            # 尝试带止损止盈的下单
            order_params = {
                'symbol': symbol,
                'type': 'market',
                'side': 'buy',
                'amount': min_amount,
                'params': {
                    'stopLoss': {
                        'triggerPrice': stop_loss_price,
                        'price': stop_loss_price * 0.995,
                        'type': 'market'
                    },
                    'takeProfit': {
                        'triggerPrice': take_profit_price,
                        'price': take_profit_price * 0.995,
                        'type': 'market'
                    },
                    'tdMode': 'cross'  # 明确指定交易模式
                }
            }
            
            order = exchange.create_order(**order_params)
            print(f"   ✅ 带止损止盈下单成功!")
            
        except Exception as e:
            print(f"   ❌ 止损止盈订单失败: {e}")
            print("   💡 建议: 先下普通单，然后单独设置止损止盈")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    test_fix()