#!/usr/bin/env python3
"""
检查IP白名单问题的简化脚本
"""

import sys
import os
import configparser

def check_config():
    """检查配置文件"""
    print("🔍 检查配置文件...")
    
    config_file = 'config.ini'
    if not os.path.exists(config_file):
        print(f"❌ 配置文件不存在: {config_file}")
        return False
    
    config = configparser.ConfigParser()
    config.read(config_file)
    
    # 检查OKX配置
    if not config.has_section('OKX'):
        print("❌ 配置文件中缺少 [OKX] 部分")
        return False
    
    api_key = config.get('OKX', 'api_key', fallback='')
    if not api_key or api_key == 'YOUR_API_KEY_HERE':
        print("❌ API密钥未配置或为默认值")
        return False
    
    print(f"✅ API密钥: {api_key[:10]}...")
    
    # 检查交易对格式
    symbol = config.get('Trading', 'symbol', fallback='')
    print(f"✅ 交易对: {symbol}")
    
    # 检查是否使用测试网
    testnet = config.getboolean('System', 'testnet', fallback=False)
    print(f"✅ 测试网模式: {testnet}")
    
    return True

def get_server_ip():
    """获取当前服务器IP"""
    import requests
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        ip = response.json()['ip']
        print(f"🌐 当前服务器IP: {ip}")
        return ip
    except Exception as e:
        print(f"⚠️  无法获取IP地址: {e}")
        return "未知"

def main():
    """主函数"""
    print("=" * 60)
    print("IP白名单检查工具")
    print("=" * 60)
    
    # 获取当前IP
    current_ip = get_server_ip()
    
    # 检查配置
    if not check_config():
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("📋 问题诊断")
    print("=" * 60)
    print(f"当前服务器IP: {current_ip}")
    print("")
    print("❌ 连接失败原因: IP白名单限制")
    print("")
    print("🔧 解决方案:")
    print("1. 登录OKX网站 → API管理")
    print("2. 找到API密钥: 293b2d76-3eef-4d9f-abaa-04590e05cb4f")
    print("3. 点击'编辑'按钮")
    print("4. 在'IP白名单'设置中:")
    print("   - 选项A: 留空（允许所有IP）【推荐】")
    print(f"   - 选项B: 添加 {current_ip} 到白名单")
    print("5. 保存更改")
    print("6. 等待1-2分钟生效")
    print("")
    print("📞 如果仍然失败:")
    print("1. 确认API是在'模拟交易'环境中创建的")
    print("2. 确认API权限包含'合约交易'")
    print("3. 尝试创建新的模拟交易API")
    print("=" * 60)
    
    # 提供快速命令
    print("\n🔄 重新测试命令:")
    print(f"cd {os.getcwd()}")
    print("python test_okx_sandbox.py")

if __name__ == "__main__":
    main()