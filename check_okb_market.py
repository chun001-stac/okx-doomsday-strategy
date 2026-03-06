#!/usr/bin/env python3
"""
检查OKX模拟交易是否支持OKB
"""

import ccxt
import configparser

def check_okb_market():
    """检查OKB市场是否可用"""
    # 读取配置
    config = configparser.ConfigParser()
    config.read('/root/.openclaw/workspace/freqtrade_workspace_okb/config.ini')
    
    api_key = config.get('OKX', 'api_key', fallback='')
    api_secret = config.get('OKX', 'api_secret', fallback='')
    api_password = config.get('OKX', 'api_password', fallback='')
    
    # 创建交易所连接
    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': api_secret,
        'password': api_password,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
            'sandbox': True,  # 模拟交易
        }
    })
    
    print("正在检查OKX模拟交易市场...")
    
    try:
        # 加载市场数据
        markets = exchange.load_markets()
        print(f"✅ 成功加载市场，共有 {len(markets)} 个交易对")
        
        # 查找OKB相关交易对
        okb_markets = []
        for symbol, market in markets.items():
            if 'OKB' in symbol.upper():
                okb_markets.append((symbol, market))
        
        print(f"\n📊 OKB相关交易对 (共{len(okb_markets)}个):")
        for symbol, market in okb_markets:
            print(f"  {symbol}: {market.get('type', 'N/A')} - {market.get('info', {}).get('alias', 'N/A')}")
        
        if not okb_markets:
            print("❌ 未找到OKB交易对")
            print("\n📋 可用的USDT永续合约示例:")
            usdt_swap = [s for s in markets.keys() if 'USDT:USDT' in s and '/USDT:USDT' in s]
            for s in usdt_swap[:20]:  # 显示前20个
                print(f"  {s}")
            
            print(f"\n... 共 {len(usdt_swap)} 个USDT永续合约")
        
        # 测试不同格式的OKB符号
        test_symbols = [
            'OKB/USDT:USDT',      # 标准格式
            'OKB-USDT-SWAP',      # 旧格式
            'OKB/USDT',           # 简化格式
            'OKBUSDT',            # 无分隔符格式
        ]
        
        print(f"\n🔍 测试不同格式的OKB符号:")
        for symbol in test_symbols:
            try:
                if symbol in markets:
                    print(f"  ✅ {symbol}: 存在")
                else:
                    print(f"  ❌ {symbol}: 不存在")
            except:
                print(f"  ⚠️  {symbol}: 检查失败")
        
        # 检查常见山寨币是否可用
        print(f"\n🔍 检查其他常见山寨币:")
        altcoins = ['DOGE', 'XRP', 'ADA', 'DOT', 'LINK', 'UNI', 'AAVE']
        for coin in altcoins:
            symbol = f'{coin}/USDT:USDT'
            if symbol in markets:
                print(f"  ✅ {symbol}: 可用")
            else:
                # 尝试其他格式
                for fmt in [f'{coin}-USDT-SWAP', f'{coin}USDT', f'{coin}/USDT']:
                    if fmt in markets:
                        print(f"  ✅ {fmt}: 可用 (替代格式)")
                        break
                else:
                    print(f"  ❌ {coin}: 不可用")
        
        return len(okb_markets) > 0
        
    except Exception as e:
        print(f"❌ 检查市场时出错: {e}")
        return False

if __name__ == "__main__":
    check_okb_market()