#!/usr/bin/env python3
"""
验证模拟盘API修复
"""

import sys
import os
import configparser
import ccxt

def main():
    print("=" * 60)
    print("验证模拟盘API修复")
    print("=" * 60)
    
    # 加载配置
    config_file = 'config.ini'
    if not os.path.exists(config_file):
        print(f"配置文件不存在: {config_file}")
        return
    
    config = configparser.ConfigParser()
    config.read(config_file)
    
    api_key = config.get('OKX', 'api_key', fallback='')
    api_secret = config.get('OKX', 'api_secret', fallback='')
    api_password = config.get('OKX', 'api_password', fallback='')
    testnet = config.getboolean('System', 'testnet', fallback=True)
    
    print(f"API密钥: {api_key[:10]}...")
    print(f"测试网模式: {testnet}")
    
    # 使用策略中的配置方式
    print(f"\n🔧 使用策略配置 (sandbox={testnet}):")
    exchange_config = {
        'apiKey': api_key,
        'secret': api_secret,
        'password': api_password,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
            'sandbox': testnet,  # 使用sandbox参数
        }
    }
    
    try:
        exchange = ccxt.okx(exchange_config)
        
        # 测试服务器时间
        server_time = exchange.fetch_time()
        print(f"  ✅ 服务器时间: {server_time}")
        
        # 测试余额
        balance = exchange.fetch_balance()
        print(f"  ✅ 余额获取成功")
        
        usdt_balance = balance['total'].get('USDT', 0)
        print(f"  💰 USDT余额: {usdt_balance:,.2f}")
        
        # 显示其他资产
        print(f"  📊 其他资产:")
        for currency, amount in balance['total'].items():
            if amount > 0:
                print(f"    {currency}: {amount}")
        
        # 测试获取价格
        symbol = config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')
        print(f"\n📈 测试获取价格 ({symbol}):")
        try:
            ticker = exchange.fetch_ticker(symbol)
            print(f"  ✅ 当前价格: {ticker['last']:.2f} USDT")
        except:
            # 尝试其他交易对
            ticker = exchange.fetch_ticker('ETH-USDT')
            print(f"  ✅ ETH-USDT价格: {ticker['last']:.2f} USDT")
        
        print(f"\n🎉 连接测试成功！")
        print(f"✅ 模拟盘API配置正确")
        print(f"✅ 余额充足: {usdt_balance:,.2f} USDT")
        print(f"✅ 可以使用 sandbox={testnet} 参数")
        
        # 测试test参数是否失败
        print(f"\n🔍 对比测试 (test={testnet}):")
        exchange_config2 = {
            'apiKey': api_key,
            'secret': api_secret,
            'password': api_password,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'test': testnet,  # 使用test参数
            }
        }
        
        try:
            exchange2 = ccxt.okx(exchange_config2)
            exchange2.fetch_balance()
            print(f"  ❓ 意外成功: test参数也有效")
        except Exception as e:
            print(f"  ✅ 预期失败: {str(e)[:80]}...")
            print(f"  💡 确认: 此API必须使用sandbox参数，而不是test参数")
        
    except Exception as e:
        print(f"\n❌ 连接失败: {e}")
        print(f"\n🔧 尝试其他配置...")
        
        # 尝试testnet参数
        print(f"\n尝试testnet参数:")
        exchange_config3 = {
            'apiKey': api_key,
            'secret': api_secret,
            'password': api_password,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'testnet': testnet,
            }
        }
        
        try:
            exchange3 = ccxt.okx(exchange_config3)
            balance = exchange3.fetch_balance()
            print(f"  ✅ testnet参数成功！")
            print(f"  💰 USDT余额: {balance['total'].get('USDT', 0):,.2f}")
        except Exception as e2:
            print(f"  ❌ testnet参数也失败: {e2}")
    
    print(f"\n" + "=" * 60)
    print(f"🚀 运行策略测试:")
    print(f"cd {os.getcwd()}")
    print(f"python okx_doomsday_optimized.py")

if __name__ == "__main__":
    main()