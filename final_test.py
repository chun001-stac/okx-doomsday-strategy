#!/usr/bin/env python3
"""
最终测试：验证OKX模拟账户完整交易流程
"""

import ccxt
import configparser
import time
import json

def final_test():
    print("🎯 OKX模拟账户完整交易流程测试")
    print("=" * 60)
    
    # 加载配置
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    api_key = config.get('OKX', 'api_key', fallback='')
    api_secret = config.get('OKX', 'api_secret', fallback='')
    api_password = config.get('OKX', 'api_password', fallback='')
    symbol = config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')
    td_mode = config.get('System', 'td_mode', fallback='cross')
    testnet = config.getboolean('System', 'testnet', fallback=True)
    
    print(f"📋 配置:")
    print(f"   交易对: {symbol}")
    print(f"   td_mode: {td_mode}")
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
        }
    })
    
    try:
        # 1. 加载市场
        print("\n1️⃣ 加载市场数据...")
        exchange.load_markets()
        market = exchange.market(symbol)
        min_amount = market['limits']['amount']['min']
        print(f"   ✅ 市场加载成功")
        print(f"   最小下单数量: {min_amount} {market['base']}")
        
        # 2. 检查账户余额
        print("\n2️⃣ 检查账户余额...")
        balance = exchange.fetch_balance()
        usdt_balance = balance['USDT']['total'] if 'USDT' in balance else 0
        usdt_free = balance['USDT']['free'] if 'USDT' in balance else 0
        print(f"   USDT总余额: {usdt_balance}")
        print(f"   USDT可用余额: {usdt_free}")
        
        # 3. 检查当前持仓
        print("\n3️⃣ 检查当前持仓...")
        positions = exchange.fetch_positions([symbol])
        open_positions = [p for p in positions if float(p['contracts'] or 0) != 0]
        
        if open_positions:
            print(f"   ⚠️  发现{len(open_positions)}个未平仓持仓:")
            for pos in open_positions:
                print(f"      {pos['symbol']}: {pos['side']} {pos['contracts']} 合约")
        else:
            print(f"   ✅ 无未平仓持仓")
        
        # 4. 获取当前价格
        print("\n4️⃣ 获取当前价格...")
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"   当前价格: ${current_price}")
        
        # 5. 测试做多开仓
        print("\n5️⃣ 测试做多开仓...")
        try:
            # 做多参数
            buy_params = {
                'tdMode': td_mode,
                'posSide': 'long'
            }
            
            print(f"   下单参数: side=buy, amount={min_amount}, params={buy_params}")
            
            buy_order = exchange.create_order(
                symbol=symbol,
                type='market',
                side='buy',
                amount=min_amount,
                params=buy_params
            )
            
            print(f"   ✅ 做多开仓成功!")
            print(f"      订单ID: {buy_order.get('id', 'N/A')}")
            print(f"      状态: {buy_order.get('status', 'N/A')}")
            
            # 等待订单完成
            time.sleep(2)
            
            # 检查新持仓
            positions_after_buy = exchange.fetch_positions([symbol])
            open_after_buy = [p for p in positions_after_buy if float(p['contracts'] or 0) != 0]
            
            if open_after_buy:
                print(f"   📊 开仓后持仓:")
                for pos in open_after_buy:
                    print(f"      方向: {pos['side']}, 数量: {pos['contracts']} 合约")
                    
                # 6. 测试平仓
                print("\n6️⃣ 测试平仓...")
                
                # 确定平仓方向和posSide
                position = open_after_buy[0]
                close_side = 'sell' if position['side'] == 'long' else 'buy'
                close_posside = position['side']  # 与开仓相同
                close_amount = abs(float(position['contracts']))
                
                close_params = {
                    'tdMode': td_mode,
                    'posSide': close_posside
                }
                
                print(f"   平仓参数: side={close_side}, amount={close_amount}, params={close_params}")
                
                sell_order = exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side=close_side,
                    amount=close_amount,
                    params=close_params
                )
                
                print(f"   ✅ 平仓成功!")
                print(f"      订单ID: {sell_order.get('id', 'N/A')}")
                
                # 等待并确认平仓
                time.sleep(2)
                positions_after_sell = exchange.fetch_positions([symbol])
                open_after_sell = [p for p in positions_after_sell if float(p['contracts'] or 0) != 0]
                
                if not open_after_sell:
                    print(f"   ✅ 确认持仓已完全平仓")
                else:
                    print(f"   ⚠️  仍有未平仓持仓")
            
            else:
                print(f"   ⚠️  开仓后未发现持仓（可能是市价单立即成交但未显示？）")
                
        except Exception as e:
            print(f"   ❌ 做多开仓失败: {e}")
            
            # 尝试做空开仓
            print(f"\n   🔄 尝试做空开仓...")
            try:
                sell_params = {
                    'tdMode': td_mode,
                    'posSide': 'short'
                }
                
                sell_order = exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side='sell',
                    amount=min_amount,
                    params=sell_params
                )
                
                print(f"   ✅ 做空开仓成功!")
                print(f"      订单ID: {sell_order.get('id', 'N/A')}")
                
                # 立即平仓
                time.sleep(2)
                positions = exchange.fetch_positions([symbol])
                open_positions = [p for p in positions if float(p['contracts'] or 0) != 0]
                
                if open_positions:
                    position = open_positions[0]
                    close_side = 'buy'  # 平空仓
                    close_amount = abs(float(position['contracts']))
                    
                    close_order = exchange.create_order(
                        symbol=symbol,
                        type='market',
                        side=close_side,
                        amount=close_amount,
                        params={'tdMode': td_mode, 'posSide': 'short'}
                    )
                    
                    print(f"   ✅ 做空平仓成功!")
                
            except Exception as e2:
                print(f"   ❌ 做空开仓也失败: {e2}")
        
        # 7. 最终状态检查
        print("\n7️⃣ 最终状态检查...")
        final_balance = exchange.fetch_balance()
        final_usdt = final_balance['USDT']['total'] if 'USDT' in final_balance else 0
        final_positions = exchange.fetch_positions([symbol])
        final_open = [p for p in final_positions if float(p['contracts'] or 0) != 0]
        
        print(f"   最终USDT余额: {final_usdt}")
        print(f"   最终持仓数量: {len(final_open)}")
        
        if not final_open:
            print(f"   ✅ 测试完成，账户无未平仓持仓")
        
        print("\n🎉 测试完成!")
        
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    final_test()