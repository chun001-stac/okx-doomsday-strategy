#!/usr/bin/env python3
"""
测试API类型：实盘还是模拟盘
"""

import sys
import os
import configparser
import ccxt
import time

def test_api_environment(api_key, api_secret, api_password, test_net=True):
    """测试API环境"""
    env_type = '模拟' if test_net else '实盘'
    print(f"\n🔍 测试{env_type}环境...")
    print(f"配置: test={test_net}")
    
    config = {
        'apiKey': api_key,
        'secret': api_secret,
        'password': api_password,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
            'test': test_net,  # True=模拟，False=实盘
        }
    }
    
    try:
        exchange = ccxt.okx(config)
        
        # 测试1: 获取服务器时间
        server_time = exchange.fetch_time()
        print(f"  ✅ 服务器时间: {server_time}")
        
        # 测试2: 获取余额
        print("  ⏳ 获取余额...")
        try:
            balance = exchange.fetch_balance()
            
            if 'USDT' in balance['total']:
                usdt_balance = balance['total']['USDT']
                print(f"  ✅ USDT余额: {usdt_balance:,.2f}")
                
                # 判断环境类型
                if usdt_balance >= 100000:  # 模拟环境通常有10万USDT
                    print(f"  🎯 疑似模拟账户（余额较大: {usdt_balance:,.2f} USDT）")
                    return {'type': 'simulated', 'balance': usdt_balance, 'success': True}
                else:
                    print(f"  🎯 疑似实盘账户（余额: {usdt_balance:,.2f} USDT）")
                    return {'type': 'real', 'balance': usdt_balance, 'success': True}
            else:
                print("  ℹ️  USDT余额未找到，列出所有余额:")
                for currency, amount in balance['total'].items():
                    if amount > 0:
                        print(f"    {currency}: {amount}")
                return {'type': 'unknown', 'balance': 0, 'success': True}
                
        except Exception as e:
            print(f"  ❌ 获取余额失败: {e}")
            return {'type': 'error', 'balance': 0, 'success': False, 'error': str(e)}
        
    except ccxt.AuthenticationError as e:
        error_msg = str(e)
        print(f"  ❌ 认证失败: {error_msg}")
        
        # 分析错误信息
        if "IP whitelist" in error_msg:
            print(f"  💡 提示: IP白名单问题 - 当前服务器IP不在API白名单中")
        elif "Invalid API key" in error_msg:
            print(f"  💡 提示: API密钥无效 - 可能是密钥错误或环境不匹配")
        elif "Permission denied" in error_msg:
            print(f"  💡 提示: 权限不足 - API可能缺少必要权限")
        
        return {'type': 'auth_error', 'balance': 0, 'success': False, 'error': error_msg}
    except ccxt.NetworkError as e:
        print(f"  ❌ 网络错误: {e}")
        return {'type': 'network_error', 'balance': 0, 'success': False, 'error': str(e)}
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return {'type': 'other_error', 'balance': 0, 'success': False, 'error': str(e)}

def main():
    """主函数"""
    print("=" * 70)
    print("OKX API环境类型诊断工具")
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
    
    if not api_key or api_key == 'YOUR_API_KEY_HERE':
        print("❌ API密钥未配置或为默认值")
        return
    
    print(f"API密钥: {api_key[:10]}...")
    print(f"当前服务器IP: 43.128.87.161")
    print(f"交易对: {config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')}")
    print(f"测试网配置: {config.getboolean('System', 'testnet', fallback=False)}")
    
    print("\n" + "=" * 70)
    print("🧪 开始测试...")
    print("=" * 70)
    
    # 测试两种环境
    results = []
    
    # 测试1: 模拟环境
    result1 = test_api_environment(api_key, api_secret, api_password, test_net=True)
    results.append(('模拟环境', result1))
    
    # 等待2秒
    time.sleep(2)
    
    # 测试2: 实盘环境
    result2 = test_api_environment(api_key, api_secret, api_password, test_net=False)
    results.append(('实盘环境', result2))
    
    print("\n" + "=" * 70)
    print("📊 测试结果分析")
    print("=" * 70)
    
    # 分析结果
    sim_success = result1['success']
    real_success = result2['success']
    
    if sim_success and not real_success:
        print("🎉 结论: API是模拟交易环境密钥")
        print("   - 模拟环境连接成功")
        print("   - 实盘环境连接失败（正常）")
        print("\n✅ 配置正确，可以开始模拟交易")
        
    elif not sim_success and real_success:
        print("🎉 结论: API是实盘环境密钥")
        print("   - 模拟环境连接失败")
        print("   - 实盘环境连接成功")
        print("\n⚠️  注意: 这是实盘API，不能用于模拟交易")
        print("   请在OKX模拟交易环境创建新的API")
        
    elif sim_success and real_success:
        print("🤔 结论: API在两个环境都能连接（罕见情况）")
        print("   可能是特殊权限API")
        print("\n📋 建议检查余额判断环境:")
        sim_balance = result1.get('balance', 0)
        real_balance = result2.get('balance', 0)
        print(f"   模拟环境余额: {sim_balance:,.2f} USDT")
        print(f"   实盘环境余额: {real_balance:,.2f} USDT")
        
    else:
        print("❌ 结论: API在两个环境都连接失败")
        print("\n🔧 可能原因:")
        print("1. API密钥错误")
        print("2. IP白名单限制（两个环境都限制）")
        print("3. API被禁用")
        print("4. 网络问题")
        
        # 显示详细错误
        if 'error' in result1:
            print(f"\n模拟环境错误: {result1['error']}")
        if 'error' in result2:
            print(f"实盘环境错误: {result2['error']}")
    
    print("\n" + "=" * 70)
    print("🚀 下一步建议")
    print("=" * 70)
    
    if not sim_success and 'IP whitelist' in str(result1.get('error', '')):
        print("1. 📍 IP白名单问题")
        print(f"   当前服务器IP: 43.128.87.161")
        print("   登录OKX → API管理 → 编辑API → IP白名单")
        print("   选项A: 留空（允许所有IP）【推荐】")
        print("   选项B: 添加 43.128.87.161")
        print("   保存后等待5分钟生效")
        
    elif not sim_success and 'Invalid API key' in str(result1.get('error', '')):
        print("1. 🔑 API密钥问题")
        print("   确认API是在OKX模拟交易环境创建的")
        print("   确认API权限包含'合约交易'")
        
    elif real_success and not sim_success:
        print("1. 🔄 创建新的模拟交易API")
        print("   进入OKX模拟交易环境（不是实盘）")
        print("   创建新API，权限：合约交易、交易")
        print("   IP白名单留空，获取新密钥更新config.ini")
    
    print("\n2. 🔧 重新测试命令:")
    print(f"   cd {os.getcwd()}")
    print(f"   python {__file__}")
    
    print("\n3. 🚀 成功验证后运行:")
    print(f"   python okx_doomsday_optimized.py")

if __name__ == "__main__":
    main()