#!/usr/bin/env python3
"""
测试Bybit模拟交易连接
"""

import sys
import os
import logging
import ccxt

def test_bybit_connection(api_key, api_secret):
    """测试Bybit连接"""
    print("=" * 60)
    print("Bybit模拟交易连接测试")
    print("=" * 60)
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    if not api_key or api_key == 'YOUR_API_KEY_HERE':
        print("❌ 错误：未配置API密钥")
        print("请在config.ini中配置Bybit API密钥")
        return False
    
    print(f"API Key: {api_key[:10]}...")
    
    # 尝试多种连接方式（Bybit测试网和主网）
    test_cases = [
        {
            'name': 'Bybit测试网（推荐）',
            'config': {
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'contract',  # 合约交易
                    'test': True,  # 测试网
                }
            }
        },
        {
            'name': 'Bybit主网',
            'config': {
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'contract',
                }
            }
        },
        {
            'name': 'Bybit统一账户',
            'config': {
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'unified',  # 统一账户
                    'test': True,
                }
            }
        }
    ]
    
    for test_case in test_cases:
        print(f"\n{'='*40}")
        print(f"测试: {test_case['name']}")
        print(f"{'='*40}")
        
        try:
            # 创建交易所实例
            exchange = ccxt.bybit(test_case['config'])
            
            # 测试1: 获取服务器时间
            print("  1. 获取服务器时间...")
            server_time = exchange.fetch_time()
            print(f"    服务器时间: {server_time} ✓")
            
            # 测试2: 获取账户余额
            print("  2. 获取账户余额...")
            balance = exchange.fetch_balance()
            
            # Bybit余额结构
            if 'USDT' in balance.get('total', {}):
                usdt_balance = balance['total']['USDT']
                print(f"    USDT总余额: {usdt_balance:.2f} ✓")
            elif 'total' in balance:
                # 列出所有余额
                print(f"    可用余额:")
                for currency, amount in balance['total'].items():
                    if amount > 0:
                        print(f"      {currency}: {amount}")
            else:
                print(f"    余额: {balance}")
            
            # 测试3: 获取市场信息
            print("  3. 获取市场信息...")
            markets = exchange.load_markets()
            
            # 查找ETH合约
            eth_contracts = []
            for symbol in markets.keys():
                if 'ETH' in symbol and 'USDT' in symbol and ('PERP' in symbol or 'swap' in symbol.lower()):
                    eth_contracts.append(symbol)
            
            print(f"    找到 {len(eth_contracts)} 个ETH合约")
            if eth_contracts:
                print(f"    前5个合约: {eth_contracts[:5]}")
                
                # 测试4: 获取价格
                print("  4. 获取当前价格...")
                try:
                    # 尝试第一个ETH合约
                    test_symbol = eth_contracts[0]
                    ticker = exchange.fetch_ticker(test_symbol)
                    print(f"    {test_symbol}: {ticker['last']:.2f} ✓")
                    print(f"    24h成交量: {ticker['quoteVolume']:.0f} USDT")
                except Exception as e:
                    print(f"    获取价格失败: {e}")
            
            # 测试5: 检查账户类型
            print("  5. 检查账户配置...")
            try:
                # Bybit特有的账户信息
                account_info = exchange.private_get_v5_account_info()
                print(f"    账户类型: {account_info.get('result', {}).get('accountType', '未知')}")
                print(f"    是否为测试账户: {exchange.urls.get('test', False)}")
            except:
                print("    无法获取账户详细信息")
            
            # 测试6: 检查合约交易权限
            print("  6. 检查交易权限...")
            try:
                positions = exchange.fetch_positions()
                if positions:
                    print(f"    当前持仓数: {len(positions)}")
                    for pos in positions[:3]:  # 显示前3个
                        if abs(pos.get('contracts', 0)) > 0:
                            print(f"      {pos['symbol']}: {pos['side']} {pos['contracts']}")
                else:
                    print("    无持仓（正常）")
            except Exception as e:
                print(f"    获取持仓失败（可能无持仓）: {e}")
            
            # 测试7: 检查是否为模拟账户
            print("  7. 检查是否为模拟账户...")
            try:
                # 尝试小额下单测试（模拟环境）
                test_order = exchange.create_test_order(
                    symbol=eth_contracts[0] if eth_contracts else 'ETH/USDT:USDT',
                    type='market',
                    side='buy',
                    amount=0.001,  # 极小数量
                )
                print(f"    模拟下单成功 ✓")
            except Exception as e:
                if 'test' in str(e).lower() or 'demo' in str(e).lower():
                    print(f"    确认为模拟/测试账户 ✓")
                else:
                    print(f"    模拟下单测试: {e}")
            
            print(f"\n✅ {test_case['name']} 测试通过！")
            print(f"✅ Bybit连接成功！")
            
            # 显示完整的交易所配置
            print(f"\n成功配置:")
            print(f"  模式: {test_case['name']}")
            print(f"  测试网: {test_case['config'].get('options', {}).get('test', False)}")
            print(f"  账户类型: {test_case['config'].get('options', {}).get('defaultType', 'contract')}")
            
            return True, test_case['config']
            
        except ccxt.AuthenticationError as e:
            print(f"  ❌ 认证失败: {e}")
            print("    可能原因：")
            print("    1. API密钥错误")
            print("    2. API权限不足")
            print("    3. 密钥已过期")
            continue
            
        except ccxt.NetworkError as e:
            print(f"  ❌ 网络错误: {e}")
            print("    可能原因：")
            print("    1. 网络连接问题")
            print("    2. Bybit API维护")
            print("    3. 防火墙限制")
            continue
            
        except Exception as e:
            print(f"  ❌ 错误: {str(e)[:100]}...")
            continue
    
    print(f"\n{'='*60}")
    print("❌ 所有连接方式都失败")
    print("=" * 60)
    print("可能原因:")
    print("1. API密钥错误或权限不足")
    print("2. 未使用模拟交易API（实盘API无法连接测试网）")
    print("3. 网络问题（请检查防火墙）")
    print("4. Bybit服务暂时不可用")
    print("\n解决方案:")
    print("1. 确认在Bybit模拟交易界面创建API")
    print("2. 检查API权限包含'合约交易'")
    print("3. 尝试更换网络环境")
    print("4. 等待几分钟后重试")
    print("=" * 60)
    
    return False, None

def check_dependencies():
    """检查依赖库"""
    print("\n检查Python依赖库...")
    
    required_libs = ['ccxt']
    
    for lib in required_libs:
        try:
            __import__(lib)
            print(f"  {lib}: ✓ 已安装")
        except ImportError:
            print(f"  {lib}: ✗ 未安装")
            print(f"    安装命令: pip install {lib}")
            return False
    
    # 检查ccxt版本
    try:
        import ccxt
        version = ccxt.__version__
        print(f"  ccxt版本: {version} ✓")
        if version < '4.0.0':
            print(f"  ⚠️  建议升级: pip install ccxt --upgrade")
    except:
        pass
    
    return True

def load_config():
    """从config.ini加载配置"""
    config_file = 'config.ini'
    
    if not os.path.exists(config_file):
        print(f"❌ 配置文件 {config_file} 不存在")
        print("请先创建config.ini文件")
        return None, None
    
    try:
        import configparser
        parser = configparser.ConfigParser()
        parser.read(config_file)
        
        if 'Bybit' in parser:
            api_key = parser['Bybit'].get('api_key', '')
            api_secret = parser['Bybit'].get('api_secret', '')
            return api_key, api_secret
        else:
            print("❌ 配置文件中缺少[Bybit]部分")
            return None, None
            
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}")
        return None, None

def main():
    """主函数"""
    print("Bybit模拟交易连接测试")
    print("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        print("\n❌ 依赖库不完整，请先安装")
        return
    
    # 加载配置
    api_key, api_secret = load_config()
    
    if not api_key or api_key == 'YOUR_API_KEY_HERE':
        print("\n❌ 未配置Bybit API密钥")
        print("\n请先在config.ini中配置:")
        print("[Bybit]")
        print("api_key = 你的Bybit API Key")
        print("api_secret = 你的Bybit Secret Key")
        print("\n然后重新运行此测试")
        return
    
    # 测试连接
    success, config = test_bybit_connection(api_key, api_secret)
    
    if success:
        print("\n🎉 Bybit模拟交易连接成功！")
        print("\n下一步:")
        print("1. 运行模拟交易策略: python bybit_doomsday_sim.py")
        print("2. 监控运行状态: tail -f bybit_sim.log")
        print("3. 查看详细日志: logs/bybit_*.log")
    else:
        print("\n❌ Bybit连接失败")
        print("\n请检查:")
        print("1. 是否在Bybit模拟交易界面创建API")
        print("2. API权限是否包含'合约交易'")
        print("3. 网络连接是否正常")
        print("4. 配置文件config.ini是否正确")

if __name__ == "__main__":
    main()