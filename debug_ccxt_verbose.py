#!/usr/bin/env python3
"""
调试ccxt详细请求
"""

import ccxt
import os
import configparser
import logging

# 启用详细日志
logging.basicConfig(level=logging.DEBUG)

def debug_ccxt_verbose():
    """调试ccxt详细请求"""
    print("🔍 调试ccxt详细请求")
    
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
    
    # 初始化交易所（启用详细模式）
    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': api_secret,
        'password': api_password,
        'enableRateLimit': True,
        'verbose': True,  # 关键：启用详细日志
        'options': {
            'defaultType': 'swap',
            'sandbox': testnet,
        }
    })
    
    try:
        print(f"\n1️⃣ 测试余额查询...")
        print(f"   ccxt将发送请求，查看控制台输出...")
        
        # 查询余额
        balance = exchange.fetch_balance()
        print(f"\n   余额查询结果:")
        print(f"   总余额: {balance.get('total', {})}")
        print(f"   USDT余额: {balance['total'].get('USDT', 0)}")
        
        # 检查是否有info字段
        if 'info' in balance:
            print(f"\n   原始API响应:")
            print(f"   {balance['info'][:500]}...")
        
        print(f"\n2️⃣ 测试获取持仓...")
        positions = exchange.fetch_positions([symbol])
        print(f"   持仓数量: {len(positions)}")
        
        print(f"\n3️⃣ 测试获取ticker...")
        ticker = exchange.fetch_ticker(symbol)
        print(f"   当前价格: {ticker['last']}")
        
        print(f"\n4️⃣ 尝试下单（将显示详细请求）...")
        try:
            # 获取最小数量
            market = exchange.market(symbol)
            min_amount = market['limits']['amount']['min']
            
            print(f"   最小下单数量: {min_amount}")
            print(f"   准备下单...查看控制台详细请求日志")
            
            # 尝试下单（预计会失败，但可以看到请求）
            order = exchange.create_order(
                symbol=symbol,
                type='market',
                side='buy',
                amount=min_amount,
                params={'tdMode': 'cross'}
            )
            print(f"   下单结果: {order.get('id', '失败')}")
            
        except Exception as e:
            print(f"   下单失败（预期中）: {e}")
            print(f"   错误详情已记录在详细日志中")
        
        print(f"\n📝 分析：")
        print(f"   查看上面的详细日志，注意：")
        print(f"   1. 请求URL和端点")
        print(f"   2. 请求头（特别是x-simulated-trading）")
        print(f"   3. 请求体参数")
        print(f"   4. 响应内容")
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")

if __name__ == "__main__":
    debug_ccxt_verbose()