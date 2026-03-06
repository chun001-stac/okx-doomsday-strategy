#!/usr/bin/env python3
"""
测试OKX API连接脚本
用于验证API密钥是否正确，网络是否通畅
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from okx_doomsday_trader import load_config
import ccxt
import logging

def test_okx_connection():
    """测试OKX连接"""
    print("=" * 60)
    print("OKX API连接测试")
    print("=" * 60)
    
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # 加载配置
    try:
        config = load_config()
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        print("请确保config.ini文件存在且格式正确")
        return False
    
    # 检查API密钥
    if config.api_key in ['', 'YOUR_API_KEY_HERE']:
        print("错误：未配置API密钥")
        print("请修改config.ini中的[OKX]部分")
        return False
    
    print(f"API Key: {config.api_key[:10]}...")
    print(f"Symbol: {config.symbol}")
    print(f"杠杆: {config.leverage}x")
    
    # 初始化交易所
    try:
        exchange = ccxt.okx({
            'apiKey': config.api_key,
            'secret': config.api_secret,
            'password': config.api_password,
            'enableRateLimit': True,
            'options': {'defaultType': 'swap'},
        })
        
        print("\n1. 测试连接...")
        
        # 测试1: 获取服务器时间
        server_time = exchange.fetch_time()
        print(f"  服务器时间: {server_time} ✓")
        
        # 测试2: 获取余额
        print("\n2. 获取账户余额...")
        balance = exchange.fetch_balance()
        
        if 'USDT' in balance['total']:
            usdt_balance = balance['total']['USDT']
            print(f"  USDT总余额: {usdt_balance:.2f} ✓")
        else:
            print("  USDT余额: 未找到")
        
        # 测试3: 获取交易对信息
        print("\n3. 获取交易对信息...")
        markets = exchange.load_markets()
        
        if config.symbol in markets:
            market = markets[config.symbol]
            print(f"  交易对: {config.symbol} ✓")
            print(f"  最小数量: {market['limits']['amount']['min']}")
            print(f"  价格精度: {market['precision']['price']}")
        else:
            print(f"  警告: 交易对 {config.symbol} 未找到")
            # 尝试查找可用的ETH合约
            eth_markets = [s for s in markets.keys() if 'ETH' in s and 'USDT' in s and 'swap' in s]
            if eth_markets:
                print(f"  可用的ETH合约: {eth_markets[:3]}")
        
        # 测试4: 获取当前价格
        print("\n4. 获取当前价格...")
        ticker = exchange.fetch_ticker(config.symbol)
        print(f"  最新价格: {ticker['last']:.2f} ✓")
        print(f"  24h成交量: {ticker['quoteVolume']:.0f} USDT")
        
        # 测试5: 获取持仓
        print("\n5. 获取当前持仓...")
        try:
            positions = exchange.fetch_positions([config.symbol])
            if positions:
                for pos in positions:
                    if pos['symbol'] == config.symbol.replace('/', '').replace(':', ''):
                        print(f"  持仓方向: {pos['side']}")
                        print(f"  持仓数量: {pos['contracts']}")
                        print(f"  入场价格: {pos['entryPrice']}")
                        print(f"  未实现盈亏: {pos['unrealizedPnl']:.2f} USDT")
            else:
                print("  无持仓")
        except Exception as e:
            print(f"  获取持仓失败（可能无持仓）: {e}")
        
        # 测试6: 设置杠杆
        print("\n6. 测试杠杆设置...")
        try:
            exchange.set_leverage(
                leverage=config.leverage,
                symbol=config.symbol
            )
            print(f"  杠杆设置成功: {config.leverage}x ✓")
        except Exception as e:
            print(f"  杠杆设置失败: {e}")
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！API连接正常")
        print("=" * 60)
        
        return True
        
    except ccxt.AuthenticationError as e:
        print(f"\n❌ 认证失败: {e}")
        print("请检查：")
        print("1. API密钥是否正确")
        print("2. API密钥是否已启用合约交易权限")
        print("3. 交易密码是否正确")
        return False
        
    except ccxt.NetworkError as e:
        print(f"\n❌ 网络错误: {e}")
        print("请检查网络连接")
        return False
        
    except Exception as e:
        print(f"\n❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_requirements():
    """检查依赖库"""
    print("\n检查Python依赖库...")
    
    required_libs = ['ccxt', 'pandas', 'numpy']
    
    for lib in required_libs:
        try:
            __import__(lib)
            print(f"  {lib}: ✓ 已安装")
        except ImportError:
            print(f"  {lib}: ✗ 未安装")
            print(f"    安装命令: pip install {lib}")
            return False
    
    # 检查TA-Lib
    try:
        import talib
        print(f"  TA-Lib: ✓ 已安装")
    except ImportError:
        print(f"  TA-Lib: ✗ 未安装")
        print("    安装可能较复杂，参考README.md中的安装说明")
        print("    或使用: pip install TA-Lib")
    
    return True

def main():
    """主函数"""
    print("OKX末日战车交易系统 - 连接测试")
    print("=" * 60)
    
    # 检查依赖
    if not check_requirements():
        print("\n❌ 依赖库不完整，请先安装")
        return
    
    # 测试连接
    success = test_okx_connection()
    
    if success:
        print("\n🎉 准备就绪！下一步：")
        print("1. 运行测试信号生成: python test_signal_generator.py")
        print("2. 测试模式运行: python okx_doomsday_trader.py")
        print("3. 实盘前修改config.ini: enable_trading = true")
    else:
        print("\n❌ 连接测试失败，请检查以上错误")

if __name__ == "__main__":
    main()