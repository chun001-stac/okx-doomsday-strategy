#!/usr/bin/env python3
"""
测试OKX下单功能
"""

import ccxt
import sys
import os

def test_order():
    """测试下单"""
    print("🔍 测试OKX下单功能")
    
    # 加载配置
    config_file = 'config.ini'
    if not os.path.exists(config_file):
        print("❌ 配置文件不存在")
        return
    
    import configparser
    config = configparser.ConfigParser()
    config.read(config_file)
    
    api_key = config.get('OKX', 'api_key', fallback='')
    api_secret = config.get('OKX', 'api_secret', fallback='')
    api_password = config.get('OKX', 'api_password', fallback='')
    symbol = config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')
    leverage = config.getint('Trading', 'leverage', fallback=10)
    testnet = config.getboolean('System', 'testnet', fallback=True)
    
    if not api_key:
        print("❌ API密钥未配置")
        return
    
    print(f"📋 配置信息:")
    print(f"   交易对: {symbol}")
    print(f"   杠杆: {leverage}")
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
        print("\n🔄 测试账户连接...")
        balance = exchange.fetch_balance()
        usdt_balance = balance['total'].get('USDT', 0)
        print(f"✅ 连接成功")
        print(f"   账户余额: {usdt_balance:,.2f} USDT")
        
        # 检查持仓
        print("\n📊 检查持仓...")
        positions = exchange.fetch_positions([symbol])
        open_positions = []
        for pos in positions:
            if pos['symbol'] == symbol and abs(float(pos.get('contracts', 0))) > 0.001:
                open_positions.append(pos)
        
        if open_positions:
            print(f"⚠️  当前有持仓: {len(open_positions)} 个")
            for pos in open_positions:
                print(f"   - {pos['symbol']}: {pos['contracts']} 合约")
        else:
            print("✅ 无持仓")
        
        # 获取当前价格
        print("\n💰 获取市场数据...")
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"   当前价格: {current_price}")
        
        # 测试1: 简单下单（最小数量）
        print("\n🧪 测试1: 简单下单 (最小数量)")
        
        # 计算最小下单数量 (0.001 ETH)
        min_amount = 0.001
        
        try:
            # 尝试买入最小数量
            print(f"   尝试买入 {min_amount} {symbol}...")
            
            # 简单下单，不带止损止盈
            order_params = {
                'symbol': symbol,
                'type': 'market',
                'side': 'buy',
                'amount': min_amount,
            }
            
            print(f"   下单参数: {order_params}")
            
            # 检查是否启用交易
            enable_trading = config.getboolean('System', 'enable_trading', fallback=False)
            if not enable_trading:
                print("⚠️  交易未启用 (enable_trading=false)")
                print("   修改 config.ini 中 enable_trading = true")
                return
            
            order = exchange.create_order(**order_params)
            print(f"✅ 下单成功!")
            print(f"   订单ID: {order.get('id', 'N/A')}")
            print(f"   状态: {order.get('status', 'N/A')}")
            
            # 取消订单（如果是限价单）
            if order.get('status') in ['open', 'new']:
                print("\n🔄 取消测试订单...")
                exchange.cancel_order(order['id'], symbol)
                print("✅ 订单已取消")
            
        except Exception as e:
            print(f"❌ 下单失败: {e}")
            
            # 尝试不同方式
            print("\n🔄 尝试不同下单方式...")
            try:
                # 尝试不同的合约类型
                print("   尝试使用不同参数...")
                
                # 使用更简单的参数
                simple_order = exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side='buy',
                    amount=min_amount,
                    params={}
                )
                print(f"✅ 简化下单成功: {simple_order.get('id', 'N/A')}")
            except Exception as e2:
                print(f"❌ 简化下单也失败: {e2}")
                
                # 尝试检查账户模式
                print("\n🔍 检查账户模式...")
                try:
                    account_info = exchange.privateGetAccountConfig()
                    print(f"   账户模式: {account_info.get('data', [{}])[0].get('acctLv', 'N/A')}")
                    print(f"   仓位模式: {account_info.get('data', [{}])[0].get('posMode', 'N/A')}")
                except Exception as e3:
                    print(f"   无法获取账户信息: {e3}")
        
        # 测试2: 检查下单所需参数
        print("\n📝 测试2: 检查市场信息...")
        try:
            market = exchange.market(symbol)
            print(f"   最小下单数量: {market.get('limits', {}).get('amount', {}).get('min', '未知')}")
            print(f"   价格精度: {market.get('precision', {}).get('price', '未知')}")
            print(f"   数量精度: {market.get('precision', {}).get('amount', '未知')}")
            print(f"   合约类型: {market.get('type', '未知')}")
            print(f"   结算货币: {market.get('settle', '未知')}")
            print(f"   基础货币: {market.get('base', '未知')}")
        except Exception as e:
            print(f"   获取市场信息失败: {e}")
            
    except Exception as e:
        print(f"❌ 连接失败: {e}")

if __name__ == "__main__":
    test_order()