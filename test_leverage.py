#!/usr/bin/env python3
import ccxt
import configparser

# 加载配置
config = configparser.ConfigParser()
config.read('config.ini')

api_key = config['OKX']['api_key']
api_secret = config['OKX']['api_secret']
api_password = config['OKX']['api_password']
symbol = config['Trading']['symbol']
leverage = int(config['Trading']['leverage'])
margin_mode = config['Trading']['margin_mode']
td_mode = config.get('System', 'td_mode', fallback='cross')

# 创建交易所连接
exchange = ccxt.okx({
    'apiKey': api_key,
    'secret': api_secret,
    'password': api_password,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap',
        'sandbox': True,
    }
})

print(f"测试杠杆设置:")
print(f"交易对: {symbol}")
print(f"杠杆: {leverage}x")
print(f"保证金模式: {margin_mode}")
print(f"交易模式: {td_mode}")
print()

# 加载市场
exchange.load_markets()

# 测试多种参数组合
test_cases = [
    {"args": (leverage, symbol), "desc": "基础调用"},
    {"args": (leverage, symbol, {"mgnMode": "isolated"}), "desc": "mgnMode=isolated"},
    {"args": (leverage, symbol, {"mgnMode": "cross"}), "desc": "mgnMode=cross"},
    {"args": (leverage, symbol, {"mgnMode": "isolated", "tdMode": "isolated"}), "desc": "mgnMode=isolated, tdMode=isolated"},
    {"args": (leverage, symbol, {"mgnMode": "cross", "tdMode": "cross"}), "desc": "mgnMode=cross, tdMode=cross"},
    {"args": (leverage, symbol), "kwargs": {"params": {"mgnMode": "isolated", "tdMode": "isolated"}}, "desc": "params方式: mgnMode=isolated"},
    {"args": (leverage, symbol), "kwargs": {"params": {"mgnMode": "cross", "tdMode": "cross"}}, "desc": "params方式: mgnMode=cross"},
]

for i, test in enumerate(test_cases):
    print(f"\n测试 {i+1}: {test['desc']}")
    try:
        args = test.get('args', (leverage, symbol))
        kwargs = test.get('kwargs', {})
        result = exchange.set_leverage(*args, **kwargs)
        print(f"   ✅ 成功: {result}")
    except Exception as e:
        print(f"   ❌ 失败: {e}")

# 检查当前杠杆设置
print(f"\n\n检查当前杠杆设置:")
try:
    # 获取账户配置
    account_config = exchange.private_get_account_config()
    print(f"账户配置: {account_config}")
except Exception as e:
    print(f"获取账户配置失败: {e}")

# 检查市场信息
print(f"\n\n检查市场信息:")
try:
    market = exchange.market(symbol)
    print(f"交易对信息: {market['symbol']}")
    print(f"类型: {market['type']}")
    print(f"结算币: {market['settle']}")
    print(f"合约类型: {market.get('contract', 'N/A')}")
    print(f"是否永续: {market.get('swap', 'N/A')}")
except Exception as e:
    print(f"获取市场信息失败: {e}")