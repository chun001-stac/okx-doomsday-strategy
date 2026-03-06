#!/usr/bin/env python3
"""
测试OKX posSide参数的正确用法
"""

import ccxt
import configparser
import time

def test_posside_combinations():
    print("🔧 测试OKX posSide参数组合")
    
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
    
    # 加载市场
    exchange.load_markets()
    
    # 获取市场信息
    market = exchange.market(symbol)
    min_amount = market['limits']['amount']['min']
    print(f"最小下单数量: {min_amount}")
    
    # 获取当前价格
    ticker = exchange.fetch_ticker(symbol)
    current_price = ticker['last']
    print(f"当前价格: ${current_price}")
    
    # 测试组合
    test_cases = [
        # (tdMode, posSide, side, 描述)
        ('cross', 'long', 'buy', '全仓做多'),
        ('cross', 'short', 'sell', '全仓做空'),
        ('isolated', 'long', 'buy', '逐仓做多'),
        ('isolated', 'short', 'sell', '逐仓做空'),
        ('cash', 'long', 'buy', '现金做多'),
        ('cash', 'short', 'sell', '现金做空'),
        # 不加posSide的情况
        ('cross', None, 'buy', '全仓无posSide'),
        ('isolated', None, 'buy', '逐仓无posSide'),
    ]
    
    for tdMode, posSide, side, description in test_cases:
        print(f"\n🧪 测试: {description}")
        print(f"   tdMode={tdMode}, posSide={posSide}, side={side}")
        
        params = {'tdMode': tdMode}
        if posSide:
            params['posSide'] = posSide
        
        try:
            order = exchange.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=min_amount,
                params=params
            )
            
            print(f"   ✅ 成功! 订单ID: {order.get('id', 'N/A')}")
            print(f"       状态: {order.get('status', 'N/A')}")
            
            # 取消订单（如果是限价单）
            if order.get('status') in ['open', 'new']:
                exchange.cancel_order(order['id'], symbol)
                print("       订单已取消")
            
            # 记录成功的组合
            print(f"\n🎯 找到有效组合: tdMode={tdMode}, posSide={posSide}")
            return tdMode, posSide
            
        except Exception as e:
            error_msg = str(e)
            print(f"   ❌ 失败")
            
            # 提取错误代码
            if '51000' in error_msg:
                if 'posSide' in error_msg:
                    print("       错误: posSide参数错误")
                elif 'tdMode' in error_msg:
                    print("       错误: tdMode参数错误")
                else:
                    print(f"       错误: {error_msg}")
            else:
                print(f"       错误: {error_msg}")
        
        time.sleep(1)  # 避免频率限制
    
    print("\n❌ 所有组合都失败了")
    return None, None

def test_simple_order():
    """测试最简单的下单方式"""
    print("\n🔧 测试最简单下单方式")
    
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
    
    exchange.load_markets()
    market = exchange.market(symbol)
    min_amount = market['limits']['amount']['min']
    
    print(f"尝试最简单的下单: 只传symbol, type, side, amount")
    try:
        order = exchange.create_order(
            symbol=symbol,
            type='market',
            side='buy',
            amount=min_amount
        )
        print(f"✅ 成功! 不需要额外参数")
        print(f"   订单ID: {order.get('id', 'N/A')}")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("OKX posSide参数测试")
    print("=" * 60)
    
    # 先测试最简单方式
    simple_success = test_simple_order()
    
    if not simple_success:
        # 测试各种组合
        tdMode, posSide = test_posside_combinations()
        
        if tdMode and posSide:
            print(f"\n🎉 推荐配置:")
            print(f"   td_mode = {tdMode}")
            print(f"   下单时需要添加: params={{'tdMode': '{tdMode}', 'posSide': '{posSide}'}}")
        else:
            print("\n⚠️  未找到有效组合，需要进一步调试")
    
    print("\n🔍 检查账户配置...")
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    api_key = config.get('OKX', 'api_key', fallback='')
    api_secret = config.get('OKX', 'api_secret', fallback='')
    api_password = config.get('OKX', 'api_password', fallback='')
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
    
    try:
        # 获取账户配置
        account_config = exchange.private_get_account_config()
        data = account_config.get('data', [{}])[0]
        print(f"   账户级别: {data.get('acctLv', 'N/A')}")
        print(f"   仓位模式: {data.get('posMode', 'N/A')}")
        print(f"   权限: {data.get('perm', 'N/A')}")
        
        # 检查是否支持交易
        if 'trade' not in data.get('perm', ''):
            print("   ⚠️  账户权限不足: 不支持交易")
    except Exception as e:
        print(f"   ❌ 获取账户配置失败: {e}")