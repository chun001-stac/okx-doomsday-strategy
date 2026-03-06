#!/usr/bin/env python3
"""
测试正确的数量计算
"""

import ccxt
import os
import configparser

def test_correct_quantity():
    """测试正确的合约数量计算"""
    print("🧮 测试正确的合约数量计算")
    
    # 加载配置
    config = configparser.ConfigParser()
    config.read('config_clean.ini')
    
    api_key = config.get('OKX', 'api_key', fallback='')
    api_secret = config.get('OKX', 'api_secret', fallback='')
    api_password = config.get('OKX', 'api_password', fallback='')
    symbol = config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')
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
    
    try:
        # 获取市场信息
        market = exchange.market(symbol)
        print(f"📊 市场信息:")
        print(f"   合约面值(ctVal): {market.get('contractSize', '未知')}")
        print(f"   最小下单数量(minSz): {market.get('limits', {}).get('amount', {}).get('min', '未知')}")
        print(f"   价格精度: {market.get('precision', {}).get('price', '未知')}")
        print(f"   数量精度: {market.get('precision', {}).get('amount', '未知')}")
        
        # 获取合约详细信息
        print(f"\n🔍 获取合约详细信息...")
        instruments = exchange.public_get_public_instruments({
            'instType': 'SWAP',
            'instId': symbol
        })
        
        if instruments.get('data'):
            inst_info = instruments['data'][0]
            ct_val = float(inst_info.get('ctVal', 1))
            min_sz = float(inst_info.get('minSz', 0.01))
            lot_sz = float(inst_info.get('lotSz', 0.01))
            
            print(f"   合约面值(ctVal): {ct_val}")
            print(f"   最小下单量(minSz): {min_sz}")
            print(f"   数量步长(lotSz): {lot_sz}")
            print(f"   合约类型(ctType): {inst_info.get('ctType', '未知')}")
            print(f"   合约乘数(ctMult): {inst_info.get('ctMult', '未知')}")
            print(f"   合约价值(ctValCcy): {inst_info.get('ctValCcy', '未知')}")
            
            # 计算正确的下单数量
            print(f"\n🧮 数量计算:")
            
            # 场景1: 买0.001 ETH价值
            eth_amount = 0.001
            contracts_needed = eth_amount / ct_val
            print(f"   场景1: 买{eth_amount} ETH价值")
            print(f"     需要合约数量: {contracts_needed:.6f}")
            print(f"     是否满足最小数量: {contracts_needed >= min_sz}")
            
            # 场景2: 使用最小合约数量
            min_contracts = min_sz
            eth_value = min_contracts * ct_val
            print(f"\n   场景2: 最小合约数量")
            print(f"     最小合约数: {min_contracts}")
            print(f"     对应ETH价值: {eth_value:.6f} ETH")
            
            # 测试下单
            print(f"\n🧪 测试下单...")
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            print(f"   当前价格: {current_price}")
            
            # 测试不同数量
            test_amounts = [
                min_sz,  # 最小数量
                max(min_sz * 2, 0.01),  # 稍大一点
                0.01,  # 0.01合约
                0.1,   # 0.1合约
            ]
            
            for i, amount in enumerate(test_amounts):
                print(f"\n   测试{i+1}: {amount} 个合约")
                eth_value = amount * ct_val
                usdt_value = eth_value * current_price
                print(f"     对应ETH: {eth_value:.6f} ETH")
                print(f"     对应USDT: {usdt_value:.2f} USDT")
                
                # 检查余额
                balance = exchange.fetch_balance()
                usdt_balance = balance['total'].get('USDT', 0)
                print(f"     账户余额: {usdt_balance:.2f} USDT")
                print(f"     是否足够: {usdt_balance >= usdt_value}")
                
                if usdt_balance >= usdt_value:
                    try:
                        # 尝试下单
                        order_params = {
                            'symbol': symbol,
                            'type': 'market',
                            'side': 'buy',
                            'amount': amount,
                            'params': {
                                'tdMode': 'cross',  # 先尝试cross
                            }
                        }
                        
                        print(f"     尝试下单: {order_params}")
                        order = exchange.create_order(**order_params)
                        print(f"     ✅ 下单成功!")
                        print(f"       订单ID: {order.get('id', 'N/A')}")
                        
                        # 立即取消或平仓
                        if order.get('status') in ['open', 'new']:
                            exchange.cancel_order(order['id'], symbol)
                            print(f"     ✅ 订单已取消")
                        
                        elif order.get('status') == 'closed' or order.get('filled', 0) > 0:
                            print(f"     ⚠️  市价单已成交，尝试平仓...")
                            positions = exchange.fetch_positions([symbol])
                            for pos in positions:
                                if pos['symbol'] == symbol and abs(float(pos.get('contracts', 0))) > 0.001:
                                    close_side = 'sell' if float(pos['contracts']) > 0 else 'buy'
                                    close_order = exchange.create_order(
                                        symbol=symbol,
                                        type='market',
                                        side=close_side,
                                        amount=abs(float(pos['contracts']))
                                    )
                                    print(f"     ✅ 平仓成功")
                        
                        # 成功则停止测试
                        print(f"\n🎉 找到可用的下单数量: {amount} 合约")
                        return amount
                        
                    except Exception as e:
                        error_str = str(e)
                        print(f"     ❌ 下单失败: {error_str[:100]}...")
                        
                        # 尝试其他tdMode
                        if '51010' in error_str:
                            print(f"     尝试其他tdMode...")
                            for td_mode in ['cash', 'isolated']:
                                try:
                                    order_params['params']['tdMode'] = td_mode
                                    order = exchange.create_order(**order_params)
                                    print(f"     ✅ tdMode={td_mode} 下单成功!")
                                    return amount, td_mode
                                except:
                                    pass
                else:
                    print(f"     ⚠️  余额不足，跳过测试")
        
        print(f"\n❌ 所有数量测试都失败")
        print(f"   建议:")
        print(f"   1. 确认合约数量计算正确")
        print(f"   2. 检查手动下单的参数")
        print(f"   3. 可能需要特殊的下单方式")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    test_correct_quantity()