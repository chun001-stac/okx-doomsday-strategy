#!/usr/bin/env python3
"""
诊断模拟盘API问题
"""

import sys
import os
import configparser
import ccxt
import time
import json

def test_api_with_various_settings(api_key, api_secret, api_password):
    """使用多种设置测试API"""
    print("🧪 使用多种配置测试模拟盘API...")
    
    test_cases = [
        # 模拟环境测试（test=True）
        {'name': '模拟环境 (test=True)', 'options': {'defaultType': 'swap', 'test': True}},
        {'name': '模拟环境 (sandbox=True)', 'options': {'defaultType': 'swap', 'sandbox': True}},
        {'name': '模拟环境 (testnet=True)', 'options': {'defaultType': 'swap', 'testnet': True}},
        
        # 实盘环境测试（test=False）
        {'name': '实盘环境 (test=False)', 'options': {'defaultType': 'swap', 'test': False}},
        {'name': '实盘环境 (默认)', 'options': {'defaultType': 'swap'}},
        
        # 特殊测试
        {'name': '模拟环境无合约类型', 'options': {'test': True}},
        {'name': '仅test参数', 'options': {'test': True, 'defaultType': 'spot'}},
    ]
    
    results = []
    
    for test in test_cases:
        print(f"\n🔍 测试: {test['name']}")
        print(f"   选项: {test['options']}")
        
        try:
            exchange = ccxt.okx({
                'apiKey': api_key,
                'secret': api_secret,
                'password': api_password,
                'enableRateLimit': True,
                'options': test['options']
            })
            
            # 测试1: 服务器时间
            server_time = exchange.fetch_time()
            print(f"   ✅ 服务器时间: {server_time}")
            
            # 测试2: 获取余额
            try:
                balance = exchange.fetch_balance()
                print(f"   ✅ 余额获取成功")
                
                # 分析余额
                usdt_balance = balance['total'].get('USDT', 0)
                print(f"   💰 USDT余额: {usdt_balance:,.2f}")
                
                # 判断账户类型
                if usdt_balance >= 100000:
                    print(f"   🎯 模拟账户特征: 大额虚拟资金")
                
                # 显示其他资产
                print(f"   其他资产:")
                for currency, amount in balance['total'].items():
                    if amount > 0 and currency != 'USDT':
                        print(f"     {currency}: {amount}")
                
                results.append({
                    'name': test['name'],
                    'success': True,
                    'balance': usdt_balance,
                    'env_type': 'simulated' if usdt_balance >= 100000 else 'unknown'
                })
                
            except ccxt.AuthenticationError as e:
                error_msg = str(e)
                print(f"   ❌ 认证失败: {error_msg}")
                
                # 分析错误
                if "APIKey does not match current environment" in error_msg:
                    print(f"   💡 提示: API密钥与环境不匹配")
                    print(f"       - API可能是实盘的，但我们在模拟环境测试")
                    print(f"       - 或API是模拟的，但我们在实盘环境测试")
                elif "IP whitelist" in error_msg:
                    print(f"   💡 提示: IP白名单问题")
                elif "Permission denied" in error_msg:
                    print(f"   💡 提示: 权限不足")
                
                results.append({
                    'name': test['name'],
                    'success': False,
                    'error': error_msg
                })
                
            except Exception as e:
                print(f"   ❌ 错误: {e}")
                results.append({
                    'name': test['name'],
                    'success': False,
                    'error': str(e)
                })
                
        except Exception as e:
            print(f"   ❌ 初始化失败: {e}")
            results.append({
                'name': test['name'],
                'success': False,
                'error': str(e)
            })
    
    return results

def check_api_details(api_key, api_secret, api_password):
    """检查API详情"""
    print("\n🔍 检查API详细权限...")
    
    # 尝试获取账户信息
    for test_value in [True, False]:
        print(f"\n  使用 test={test_value}:")
        try:
            exchange = ccxt.okx({
                'apiKey': api_key,
                'secret': api_secret,
                'password': api_password,
                'enableRateLimit': True,
                'options': {'defaultType': 'swap', 'test': test_value}
            })
            
            # 尝试获取账户配置
            try:
                print("  尝试获取账户配置...")
                # 不同版本的ccxt可能有不同方法
                # 先尝试一些常见方法
                markets = exchange.load_markets()
                print(f"  市场加载成功，数量: {len(markets)}")
                
                # 尝试获取交易对列表
                eth_markets = [s for s in markets.keys() if 'ETH' in s and 'USDT' in s]
                print(f"  ETH交易对: {len(eth_markets)}个")
                if eth_markets:
                    print(f"  示例: {eth_markets[:3]}")
                    
            except Exception as e:
                print(f"  获取账户信息失败: {e}")
                
        except Exception as e:
            print(f"  连接失败: {e}")

def main():
    print("=" * 70)
    print("OKX模拟盘API诊断工具")
    print("=" * 70)
    
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
    
    if not api_key:
        print("❌ API密钥未配置")
        return
    
    print(f"API密钥: {api_key[:10]}...")
    print(f"当前服务器IP: 43.128.87.161")
    print(f"交易对: {config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')}")
    print(f"测试网配置: {config.getboolean('System', 'testnet', fallback=True)}")
    
    # 测试多种配置
    results = test_api_with_various_settings(api_key, api_secret, api_password)
    
    # 检查API详情
    check_api_details(api_key, api_secret, api_password)
    
    print("\n" + "=" * 70)
    print("📊 诊断结果分析")
    print("=" * 70)
    
    # 分析结果
    successful_tests = [r for r in results if r['success']]
    failed_tests = [r for r in results if not r['success']]
    
    print(f"成功测试: {len(successful_tests)} 个")
    print(f"失败测试: {len(failed_tests)} 个")
    
    if successful_tests:
        print("\n✅ 成功的测试配置:")
        for test in successful_tests:
            print(f"  - {test['name']}: USDT余额={test.get('balance', 0):,.2f}")
    
    if failed_tests:
        print("\n❌ 失败的测试配置:")
        for test in failed_tests:
            error = test.get('error', '未知错误')
            if "APIKey does not match current environment" in error:
                print(f"  - {test['name']}: API密钥与环境不匹配")
            else:
                print(f"  - {test['name']}: {error[:80]}...")
    
    print("\n" + "=" * 70)
    print("🚀 解决方案建议")
    print("=" * 70)
    
    # 根据结果给出建议
    if any("test=True" in str(r['name']) and r['success'] for r in results):
        print("✅ 找到可用的模拟环境配置!")
        print("\n🎯 建议:")
        print("1. 在策略中使用 test=True 选项")
        print("2. 确保 config.ini 中 testnet = true")
        print("3. 运行策略测试")
        
    elif any("test=False" in str(r['name']) and r['success'] for r in results):
        print("⚠️  API在实盘环境可用，模拟环境失败")
        print("\n🎯 可能原因:")
        print("1. API是在实盘环境创建的")
        print("2. 需要创建新的模拟交易API")
        print("3. 联系OKX客服确认API类型")
        
    else:
        print("❌ 所有配置都失败")
        print("\n🎯 根本原因:")
        print("1. API密钥错误或无效")
        print("2. API缺少合约交易权限")
        print("3. IP白名单限制（虽然已添加）")
        print("4. API被禁用")
        
        print("\n🔧 解决步骤:")
        print("1. 登录OKX模拟交易界面")
        print("2. 确认API状态为'启用'")
        print("3. 检查权限包含: ✅合约交易、✅交易")
        print("4. 确认IP白名单包含: 43.128.87.161")
        print("5. 如仍失败，创建新的模拟交易API")
    
    print("\n💡 快速测试命令:")
    print(f"cd {os.getcwd()}")
    print(f"python okx_doomsday_optimized.py")

if __name__ == "__main__":
    main()