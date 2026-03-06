#!/usr/bin/env python3
"""
检查并关闭模拟账户所有持仓
"""

import sys
import os
import configparser
import ccxt
import time

def main():
    print("=" * 60)
    print("检查并关闭模拟账户持仓")
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
    symbol = config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')
    
    print(f"API密钥: {api_key[:10]}...")
    print(f"测试网模式: {testnet}")
    print(f"交易对: {symbol}")
    
    # 初始化交易所
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
        
        # 测试连接
        server_time = exchange.fetch_time()
        print(f"✅ 服务器时间: {server_time}")
        
        # 检查余额
        balance = exchange.fetch_balance()
        usdt_balance = balance['total'].get('USDT', 0)
        print(f"💰 USDT余额: {usdt_balance:,.2f}")
        
        # 获取持仓
        print(f"\n🔍 检查持仓...")
        positions = exchange.fetch_positions([symbol])
        
        open_positions = []
        for pos in positions:
            if pos['symbol'] == symbol:
                contracts = float(pos.get('contracts', 0))
                if abs(contracts) > 0.001:
                    open_positions.append(pos)
        
        if open_positions:
            print(f"📊 发现 {len(open_positions)} 个持仓:")
            for pos in open_positions:
                symbol = pos['symbol']
                contracts = float(pos['contracts'])
                entry_price = pos.get('entryPrice', 0)
                mark_price = pos.get('markPrice', 0)
                side = 'long' if contracts > 0 else 'short'
                
                print(f"   {symbol}: {abs(contracts)} 合约 ({side})")
                print(f"   入场价: {entry_price:.2f}, 标记价: {mark_price:.2f}")
                
                # 计算盈亏
                if side == 'long':
                    pnl_pct = (mark_price - entry_price) / entry_price * 100
                else:
                    pnl_pct = (entry_price - mark_price) / entry_price * 100
                
                print(f"   盈亏: {pnl_pct:.2f}%")
            
            # 平仓
            print(f"\n🚨 开始平仓...")
            for pos in open_positions:
                symbol = pos['symbol']
                contracts = abs(float(pos['contracts']))
                side = 'long' if float(pos['contracts']) > 0 else 'short'
                
                print(f"\n  平仓 {symbol}: {contracts} 合约 ({side})")
                
                # 确定平仓方向
                order_side = 'sell' if side == 'long' else 'buy'
                
                try:
                    order = exchange.create_order(
                        symbol=symbol,
                        type='market',
                        side=order_side,
                        amount=contracts
                    )
                    print(f"  ✅ 平仓成功: {order['id']}")
                    
                    # 等待订单完成
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"  ❌ 平仓失败: {e}")
        
        else:
            print(f"✅ 无持仓，账户干净")
        
        # 再次确认持仓状态
        print(f"\n🔍 最终持仓确认...")
        positions = exchange.fetch_positions([symbol])
        remaining = [p for p in positions if float(p.get('contracts', 0)) > 0.001]
        
        if remaining:
            print(f"⚠️  仍有持仓未平: {len(remaining)}")
            for pos in remaining:
                print(f"   {pos['symbol']}: {pos.get('contracts', 0)}")
        else:
            print(f"✅ 所有持仓已平，账户准备就绪")
        
        # 获取当前价格
        ticker = exchange.fetch_ticker(symbol)
        print(f"\n📈 当前价格: {ticker['last']:.2f} USDT")
        
        print(f"\n" + "=" * 60)
        print(f"🎯 准备完成")
        print(f"   账户余额: {usdt_balance:,.2f} USDT")
        print(f"   持仓状态: 无持仓")
        print(f"   当前价格: {ticker['last']:.2f} USDT")
        print(f"   策略可以开始交易")
        print(f"=" * 60)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()