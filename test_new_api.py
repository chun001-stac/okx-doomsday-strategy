#!/usr/bin/env python3
"""
测试新的OKX模拟API
"""

import sys
import os
import configparser
import ccxt

def test_api_connection(api_key, api_secret, api_password):
    """测试API连接"""
    print("🔍 测试API连接...")
    
    # 测试不同的配置
    test_cases = [
        {
            'name': '模拟环境 (test=True)',
            'config': {
                'apiKey': api_key,
                'secret': api_secret,
                'password': api_password,
                'enableRateLimit': True,
                'options': {'defaultType': 'swap', 'test': True}
            }
        },
        {
            'name': '实盘环境 (test=False)', 
            'config': {
                'apiKey': api_key,
                'secret': api_secret,
                'password': api_password,
                'enableRateLimit': True,
                'options': {'defaultType': 'swap', 'test': False}
            }
        },
        {
            'name': '不使用test参数',
            'config': {
                'apiKey': api_key,
                'secret': api_secret,
                'password': api_password,
                'enableRateLimit': True,
                'options': {'defaultType': 'swap'}
            }
        }
    ]
    
    for test in test_cases:
        print(f"\n📋 测试: {test['name']}")
        print(f"   配置: {test['config']['options']}")
        
        try:
            exchange = ccxt.okx(test['config'])
            
            # 测试服务器时间
            server_time = exchange.fetch_time()
            print(f"   ✅ 服务器时间: {server_time}")
            
            # 测试获取余额
            try:
                balance = exchange.fetch_balance()
                print(f"   ✅ 余额获取成功")
                if 'USDT' in balance['total']:
                    usdt = balance['total']['USDT']
                    print(f"   💰 USDT余额: {usdt:,.2f}")
                    if usdt >= 100000:
                        print(f"   🎯 疑似模拟账户（大额余额）")
            except Exception as e:
                print(f"   ❌ 获取余额失败: {e}")
                
        except ccxt.AuthenticationError as e:
            print(f"   ❌ 认证失败: {e}")
        except Exception as e:
            print(f"   ❌ 错误: {e}")
    
    return False

def main():
    print("=" * 60)
    print("新OKX API连接测试")
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
    
    if not api_key or api_key == 'YOUR_API_KEY_HERE':
        print("❌ API密钥未配置或为默认值")
        return
    
    print(f"API密钥: {api_key[:10]}...")
    print(f"当前服务器IP: 43.128.87.161")
    
    # 测试连接
    test_api_connection(api_key, api_secret, api_password)
    
    print("\n" + "=" * 60)
    print("📋 问题分析")
    print("=" * 60)
    print("错误代码: 50101 - 'APIKey does not match current environment'")
    print("")
    print("🔧 可能原因:")
    print("1. API不是在OKX模拟交易环境创建的")
    print("2. API权限不足（缺少'合约交易'权限）")
    print("3. API被禁用")
    print("4. IP白名单限制（新API可能需要添加IP）")
    print("")
    print("🚀 解决方案:")
    print("1. 登录OKX模拟交易环境（不是实盘）")
    print("2. 确认API是在模拟交易界面创建的")
    print("3. 检查API权限包含: ✅合约交易、✅交易")
    print("4. 检查IP白名单: 添加 43.128.87.161 或留空")
    print("5. 确认API状态为'启用'")
    print("")
    print("💡 提示: 模拟交易API和实盘API是不同的，不能混用")

if __name__ == "__main__":
    main()