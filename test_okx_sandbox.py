#!/usr/bin/env python3
"""
测试OKX模拟交易API连接
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from okx_doomsday_trader import load_config
import ccxt
import logging

def test_okx_sandbox():
    """测试OKX模拟交易连接"""
    print("=" * 60)
    print("OKX模拟交易API连接测试")
    print("=" * 60)
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # 加载配置
    try:
        config = load_config()
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return False
    
    if config.api_key in ['', 'YOUR_API_KEY_HERE']:
        print("错误：未配置API密钥")
        return False
    
    print(f"API Key: {config.api_key[:10]}...")
    print(f"Symbol: {config.symbol}")
    
    # 尝试多种连接方式
    test_cases = [
        {
            'name': '标准模式',
            'config': {
                'apiKey': config.api_key,
                'secret': config.api_secret,
                'password': config.api_password,
                'enableRateLimit': True,
                'options': {'defaultType': 'swap'}
            }
        },
        {
            'name': '沙箱模式1',
            'config': {
                'apiKey': config.api_key,
                'secret': config.api_secret,
                'password': config.api_password,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap',
                    'sandbox': True
                }
            }
        },
        {
            'name': '沙箱模式2',
            'config': {
                'apiKey': config.api_key,
                'secret': config.api_secret,
                'password': config.api_password,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap',
                    'test': True
                }
            }
        },
        {
            'name': '模拟交易端点',
            'config': {
                'apiKey': config.api_key,
                'secret': config.api_secret,
                'password': config.api_password,
                'enableRateLimit': True,
                'options': {'defaultType': 'swap'},
                'urls': {
                    'api': {
                        'public': 'https://www.okx.com',
                        'private': 'https://www.okx.com',
                        'markets': 'https://www.okx.com'
                    }
                }
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n{'='*40}")
        print(f"测试: {test_case['name']}")
        print(f"{'='*40}")
        
        try:
            exchange = ccxt.okx(test_case['config'])
            
            # 测试1: 获取服务器时间
            server_time = exchange.fetch_time()
            print(f"  服务器时间: {server_time} ✓")
            
            # 测试2: 获取余额
            print("  获取余额...")
            balance = exchange.fetch_balance()
            
            if 'USDT' in balance['total']:
                usdt_balance = balance['total']['USDT']
                print(f"  USDT余额: {usdt_balance:.2f} ✓")
            else:
                print("  USDT余额: 未找到，列出可用余额:")
                for currency, amount in balance['total'].items():
                    if amount > 0:
                        print(f"    {currency}: {amount}")
            
            # 测试3: 获取市场信息
            print("  获取市场信息...")
            markets = exchange.load_markets()
            
            # 查找ETH合约
            eth_markets = []
            for symbol in markets.keys():
                if 'ETH' in symbol and 'USDT' in symbol:
                    eth_markets.append(symbol)
            
            print(f"  找到 {len(eth_markets)} 个ETH交易对")
            if eth_markets:
                print(f"  前5个: {eth_markets[:5]}")
            
            # 测试4: 获取当前价格
            print("  获取当前价格...")
            # 尝试使用配置的symbol，如果失败则尝试其他ETH交易对
            try:
                ticker = exchange.fetch_ticker(config.symbol)
                print(f"  {config.symbol}: {ticker['last']:.2f} ✓")
            except:
                if eth_markets:
                    ticker = exchange.fetch_ticker(eth_markets[0])
                    print(f"  {eth_markets[0]}: {ticker['last']:.2f} ✓")
                else:
                    print("  无法获取价格")
            
            # 测试5: 检查是否是模拟账户
            print("  检查账户类型...")
            try:
                account_config = exchange.fetch_account_config()
                print(f"  账户配置: {account_config}")
            except:
                print("  无法获取账户配置")
            
            print(f"\n✅ {test_case['name']} 测试通过！")
            print(f"✅ 模拟交易环境连接成功！")
            
            # 显示完整的交易所配置
            print(f"\n成功配置:")
            print(f"  模式: {test_case['name']}")
            print(f"  选项: {test_case['config'].get('options', {})}")
            
            return True, test_case['config']
            
        except ccxt.AuthenticationError as e:
            print(f"  ❌ 认证失败: {e}")
            continue
        except ccxt.NetworkError as e:
            print(f"  ❌ 网络错误: {e}")
            continue
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            continue
    
    print(f"\n{'='*60}")
    print("❌ 所有连接方式都失败")
    print("可能原因:")
    print("1. API密钥是实盘的，但我们在模拟环境测试")
    print("2. API密钥是模拟的，但需要特殊配置")
    print("3. IP白名单问题（模拟环境可能不需要）")
    print("4. 密钥权限不足（需要合约交易权限）")
    print("=" * 60)
    
    return False, None

def main():
    """主函数"""
    print("OKX模拟交易连接测试")
    print("=" * 60)
    
    success, config = test_okx_sandbox()
    
    if success:
        print("\n🎉 模拟交易连接成功！")
        print("\n下一步:")
        print("1. 修改okx_doomsday_trader.py中的交易所配置")
        print("2. 使用测试模式运行: python okx_doomsday_trader.py")
        print("3. 确认信号生成正常后，可尝试小额实盘")
    else:
        print("\n❌ 连接测试失败")
        print("\n建议:")
        print("1. 确认API密钥是模拟交易还是实盘")
        print("2. 检查API权限是否包含'合约交易'")
        print("3. 尝试在OKX网站创建新的模拟交易API")

if __name__ == "__main__":
    main()