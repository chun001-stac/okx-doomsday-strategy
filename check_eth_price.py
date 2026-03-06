#!/usr/bin/env python3
"""
检查ETH价格和动量
"""

import ccxt
import configparser
import pandas as pd

def check_eth_price():
    # 加载配置
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    api_key = config.get('OKX', 'api_key', fallback='')
    api_secret = config.get('OKX', 'api_secret', fallback='')
    api_password = config.get('OKX', 'api_password', fallback='')
    symbol = config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')
    timeframe = config.get('Strategy', 'timeframe', fallback='5m')
    momentum_period = int(config.get('Strategy', 'momentum_period', fallback='5'))
    momentum_threshold_long = float(config.get('Strategy', 'momentum_threshold_long', fallback='0.005'))
    momentum_threshold_short = float(config.get('Strategy', 'momentum_threshold_short', fallback='-0.005'))
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
    
    print(f"📊 检查ETH价格和动量")
    print(f"   交易对: {symbol}")
    print(f"   时间周期: {timeframe}")
    print(f"   动量周期: {momentum_period}")
    print(f"   做多阈值: {momentum_threshold_long*100:.2f}%")
    print(f"   做空阈值: {momentum_threshold_short*100:.2f}%")
    
    # 获取OHLCV数据
    print(f"\n📈 获取数据...")
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=momentum_period+10)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # 计算动量（价格变化百分比）
    df['price_change_pct'] = df['close'].pct_change(periods=momentum_period) * 100
    
    # 显示最新数据
    latest = df.iloc[-1]
    print(f"\n📊 最新价格数据:")
    print(f"   时间: {latest['timestamp']}")
    print(f"   价格: ${latest['close']:.2f}")
    print(f"   成交量: {latest['volume']:.2f}")
    print(f"   {momentum_period}周期动量: {latest['price_change_pct']:.2f}%")
    
    # 检查信号条件
    if latest['price_change_pct'] > momentum_threshold_long * 100:
        print(f"   ✅ 符合做多条件: {latest['price_change_pct']:.2f}% > {momentum_threshold_long*100:.2f}%")
    elif latest['price_change_pct'] < momentum_threshold_short * 100:
        print(f"   ✅ 符合做空条件: {latest['price_change_pct']:.2f}% < {momentum_threshold_short*100:.2f}%")
    else:
        print(f"   ⚠️  无信号: 动量在阈值之间 [{momentum_threshold_short*100:.2f}%, {momentum_threshold_long*100:.2f}%]")
    
    # 显示历史数据
    print(f"\n📋 最近{momentum_period}个周期:")
    for i in range(1, min(6, len(df))):
        idx = -i
        row = df.iloc[idx]
        print(f"   {row['timestamp']}: ${row['close']:.2f} (动量: {row['price_change_pct']:.2f}%)")
    
    # 建议
    print(f"\n💡 建议:")
    current_momentum = latest['price_change_pct'] / 100  # 转换为小数
    if abs(current_momentum) < 0.001:  # 小于0.1%
        print(f"   当前市场波动较小，考虑降低阈值:")
        print(f"   建议: momentum_threshold_long = 0.003 (0.3%)")
        print(f"          momentum_threshold_short = -0.003 (-0.3%)")
    else:
        print(f"   当前动量: {current_momentum:.3%}")
        if abs(current_momentum) < abs(momentum_threshold_long):
            print(f"   考虑降低阈值以获得更多信号")

if __name__ == "__main__":
    check_eth_price()