#!/usr/bin/env python3
"""
直接调用OKX API测试
绕过ccxt，直接使用requests
"""

import requests
import json
import time
import hashlib
import hmac
import base64
from datetime import datetime
import os
import configparser

def get_timestamp():
    """获取ISO格式时间戳"""
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

def sign(message, secret_key):
    """生成签名"""
    mac = hmac.new(bytes(secret_key, encoding='utf-8'), bytes(message, encoding='utf-8'), digestmod='sha256')
    return base64.b64encode(mac.digest()).decode()

def test_direct_api():
    """直接API测试"""
    print("🌐 直接调用OKX API测试")
    
    # 加载配置
    config = configparser.ConfigParser()
    config.read('config_clean.ini')
    
    api_key = config.get('OKX', 'api_key', fallback='')
    api_secret = config.get('OKX', 'api_secret', fallback='')
    api_password = config.get('OKX', 'api_password', fallback='')
    symbol = config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')
    testnet = config.getboolean('System', 'testnet', fallback=True)
    
    if not api_key or not api_secret:
        print("❌ API密钥未配置")
        return
    
    # 选择API端点
    if testnet:
        base_url = "https://www.okx.com"  # 模拟环境使用相同域名，但参数不同
        print("   使用模拟环境（sandbox参数）")
    else:
        base_url = "https://www.okx.com"
    
    print(f"📋 配置:")
    print(f"   API密钥: {api_key[:8]}...")
    print(f"   交易对: {symbol}")
    print(f"   模拟环境: {testnet}")
    
    # 测试1: 获取账户信息
    print(f"\n1️⃣ 测试获取账户信息...")
    try:
        timestamp = get_timestamp()
        method = "GET"
        request_path = "/api/v5/account/balance?ccy=USDT"
        
        message = timestamp + method + request_path
        signature = sign(message, api_secret)
        
        headers = {
            "OK-ACCESS-KEY": api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": api_password,
            "Content-Type": "application/json"
        }
        
        if testnet:
            headers["x-simulated-trading"] = "1"  # 模拟交易头
        
        url = base_url + request_path
        print(f"   请求URL: {url}")
        print(f"   请求头: {headers}")
        
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   响应状态: {response.status_code}")
        print(f"   响应内容: {response.text[:200]}...")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 获取账户信息成功")
            if data.get('data'):
                for acc in data['data']:
                    print(f"   账户: {acc.get('ccy')}, 余额: {acc.get('availBal', 0)}")
        else:
            print(f"❌ 获取账户信息失败")
            
    except Exception as e:
        print(f"❌ 获取账户信息异常: {e}")
    
    # 测试2: 尝试下单（市价单）
    print(f"\n2️⃣ 测试下单...")
    try:
        # 先获取当前价格
        ticker_url = base_url + "/api/v5/market/ticker?instId=" + symbol
        ticker_response = requests.get(ticker_url, timeout=10)
        
        if ticker_response.status_code == 200:
            ticker_data = ticker_response.json()
            if ticker_data.get('data'):
                last_price = ticker_data['data'][0]['last']
                print(f"   当前价格: {last_price}")
        
        # 准备下单数据
        timestamp = get_timestamp()
        method = "POST"
        request_path = "/api/v5/trade/order"
        
        # 构建请求体 - 尝试不同参数组合
        test_cases = [
            {
                'name': '简单市价单',
                'data': {
                    'instId': symbol,
                    'tdMode': 'cross',
                    'side': 'buy',
                    'ordType': 'market',
                    'sz': '0.01'  # 0.01个合约
                }
            },
            {
                'name': '净仓模式',
                'data': {
                    'instId': symbol,
                    'tdMode': 'net_mode',
                    'side': 'buy',
                    'ordType': 'market',
                    'sz': '0.01'
                }
            },
            {
                'name': '不带tdMode',
                'data': {
                    'instId': symbol,
                    'side': 'buy',
                    'ordType': 'market',
                    'sz': '0.01'
                }
            },
            {
                'name': '模拟环境特殊参数',
                'data': {
                    'instId': symbol,
                    'tdMode': 'cross',
                    'side': 'buy',
                    'ordType': 'market',
                    'sz': '0.01',
                    'x-simulated-trading': '1'
                }
            },
        ]
        
        for test_case in test_cases:
            print(f"\n   🧪 {test_case['name']}")
            print(f"     请求数据: {test_case['data']}")
            
            message = timestamp + method + request_path + json.dumps(test_case['data'])
            signature = sign(message, api_secret)
            
            headers = {
                "OK-ACCESS-KEY": api_key,
                "OK-ACCESS-SIGN": signature,
                "OK-ACCESS-TIMESTAMP": timestamp,
                "OK-ACCESS-PASSPHRASE": api_password,
                "Content-Type": "application/json"
            }
            
            if testnet:
                headers["x-simulated-trading"] = "1"
            
            try:
                response = requests.post(
                    base_url + request_path,
                    headers=headers,
                    json=test_case['data'],
                    timeout=10
                )
                
                print(f"     响应状态: {response.status_code}")
                print(f"     响应内容: {response.text[:200]}")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('code') == '0':
                        print(f"     ✅ 下单成功!")
                        print(f"       订单ID: {data.get('data', [{}])[0].get('ordId', 'N/A')}")
                        return test_case['data']
                    else:
                        print(f"     ❌ API错误: {data.get('msg', '未知错误')}")
                        print(f"       错误码: {data.get('code', 'N/A')}")
                else:
                    print(f"     ❌ HTTP错误: {response.status_code}")
                    
            except Exception as e:
                print(f"     ❌ 请求异常: {e}")
        
        print(f"\n❌ 所有下单测试都失败")
        
    except Exception as e:
        print(f"❌ 下单测试异常: {e}")
    
    # 测试3: 获取交易规则
    print(f"\n3️⃣ 获取交易规则...")
    try:
        instruments_url = base_url + f"/api/v5/public/instruments?instType=SWAP&instId={symbol}"
        response = requests.get(instruments_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data'):
                inst = data['data'][0]
                print(f"   合约信息:")
                print(f"     合约面值: {inst.get('ctVal')}")
                print(f"     最小下单: {inst.get('minSz')}")
                print(f"     合约类型: {inst.get('ctType')}")
                print(f"     仓位模式: {inst.get('posMode', 'N/A')}")
    except Exception as e:
        print(f"   获取交易规则失败: {e}")

if __name__ == "__main__":
    test_direct_api()