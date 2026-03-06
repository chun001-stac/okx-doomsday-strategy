#!/usr/bin/env python3
"""
多币种持仓报告发送脚本
每两小时通过Feishu发送所有币种的持仓报告
支持ETH、BTC、SOL实例
"""

import ccxt
import configparser
import subprocess
import json
import time
import glob
from datetime import datetime, timedelta
import os
import re

def analyze_daily_performance_for_instance(workspace_path):
    """分析指定实例的当日交易绩效"""
    today = datetime.now().strftime("%Y-%m-%d")
    total_trades = 0
    winning_trades = 0
    total_pnl_percent = 0.0
    pnl_entries = []  # 记录每笔盈亏百分比
    open_trades = []  # 记录开仓交易
    
    try:
        # 切换到实例工作区
        original_cwd = os.getcwd()
        os.chdir(workspace_path)
        
        # 查找日志文件（按优先级）
        log_files = []
        
        # 1. 最新的current_fixed_*.log文件（按修改时间排序）
        current_logs = glob.glob("logs/current_fixed_*.log")
        if current_logs:
            current_logs.sort(key=os.path.getmtime, reverse=True)
            # 只检查最近24小时内的文件
            for log_file in current_logs:
                if time.time() - os.path.getmtime(log_file) < 86400:  # 24小时
                    log_files.append(log_file)
        
        # 2. 最新的doomsday_fixed日志
        fixed_logs = glob.glob("logs/doomsday_fixed_*.log")
        if fixed_logs:
            # 按修改时间排序，最新的在前
            fixed_logs.sort(key=os.path.getmtime, reverse=True)
            # 只检查最近24小时内的文件
            for log_file in fixed_logs:
                if time.time() - os.path.getmtime(log_file) < 86400:  # 24小时
                    log_files.append(log_file)
        
        # 3. current_strategy.log（主日志）
        if os.path.exists("logs/current_strategy.log"):
            log_files.append("logs/current_strategy.log")
        
        # 4. 实例特定的日志文件（如current_strategy_btc.log）
        for coin in ["eth", "btc", "sol", "okb"]:
            log_name = f"logs/current_strategy_{coin}.log"
            if os.path.exists(log_name):
                log_files.append(log_name)
        
        # 5. strategy_*.log文件（循环脚本生成）
        strategy_logs = glob.glob("logs/strategy_*.log")
        if strategy_logs:
            strategy_logs.sort(key=os.path.getmtime, reverse=True)
            # 只检查最近24小时内的文件
            for log_file in strategy_logs:
                if time.time() - os.path.getmtime(log_file) < 86400:  # 24小时
                    log_files.append(log_file)
        
        # 6. 旧的日志文件（兼容性）
        if os.path.exists("logs/current_fixed.log") and "logs/current_fixed.log" not in log_files:
            log_files.append("logs/current_fixed.log")
        
        for log_file in log_files:
            if not os.path.exists(log_file):
                continue
                
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            # 查找今日的交易统计（取最新的）
            latest_total_trades = 0
            latest_win_rate = 0.0
            
            for line in lines:
                if today in line and "交易统计" in line:
                    # 解析格式: "交易统计: 1次交易, 胜率: 100.0%"
                    match = re.search(r'交易统计: (\d+)次交易, 胜率: ([\d\.]+)%', line)
                    if match:
                        latest_total_trades = int(match.group(1))
                        latest_win_rate = float(match.group(2))
            
            if latest_total_trades > 0:
                total_trades = latest_total_trades
                winning_trades = int(round(total_trades * latest_win_rate / 100))
                
                # 如果总交易数已知但胜率为0，则没有盈利交易
                if latest_win_rate == 0:
                    winning_trades = 0
            
            # 查找平仓盈亏百分比（包括盈利和亏损）
            for line in lines:
                if today in line and ("平仓盈利:" in line or "平仓亏损:" in line):
                    # 解析格式: "平仓盈利: 1.20%" 或 "平仓亏损: -5.33%"
                    match = re.search(r'平仓(?:盈利|亏损): ([\d\.\-]+)%', line)
                    if match:
                        pnl_percent = float(match.group(1))
                        pnl_entries.append(pnl_percent)
                        total_pnl_percent += pnl_percent
            
            # 查找开仓交易
            for line in lines:
                if today in line and "开仓成功:" in line:
                    open_trades.append(line.strip())
            
            # 如果没有找到交易统计，但找到了平仓记录，则尝试计算
            if total_trades == 0 and len(pnl_entries) > 0:
                total_trades = len(pnl_entries)
                # 简单估计：正值为盈利，负值为亏损
                winning_trades = sum(1 for p in pnl_entries if p > 0)
            
            # 如果既没有平仓记录也没有交易统计，但有开仓记录，则显示开仓次数
            if total_trades == 0 and len(pnl_entries) == 0 and len(open_trades) > 0:
                total_trades = len(open_trades)
                # 开仓交易尚未平仓，无法确定盈亏
                winning_trades = 0
                total_pnl_percent = 0.0
            
            # 如果在这个文件中找到了数据，就停止查找其他文件
            if total_trades > 0 or len(pnl_entries) > 0 or len(open_trades) > 0:
                break
                
        # 切回原工作目录
        os.chdir(original_cwd)
                        
    except Exception as e:
        print(f"分析日志时出错 ({workspace_path}): {e}")
    
    return total_trades, winning_trades, total_pnl_percent

def get_instance_position_report(workspace_path, instance_name):
    """获取单个实例的持仓报告"""
    original_cwd = os.getcwd()
    try:
        # 切换到实例工作区
        os.chdir(workspace_path)
        
        # 读取配置
        config = configparser.ConfigParser()
        if not os.path.exists('config.ini'):
            print(f"❌ 配置不存在: {workspace_path}/config.ini")
            return None
            
        config.read('config.ini')
        
        api_key = config.get('OKX', 'api_key', fallback='')
        api_secret = config.get('OKX', 'api_secret', fallback='')
        api_password = config.get('OKX', 'api_password', fallback='')
        symbol = config.get('Trading', 'symbol', fallback='ETH-USDT-SWAP')
        testnet = config.getboolean('System', 'testnet', fallback=True)
        
        if not api_key:
            print(f"⚠️  跳过 {instance_name} (无API配置)")
            os.chdir(original_cwd)
            return None
        
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
        
        instance_report = {
            'name': instance_name,
            'symbol': symbol,
            'balance': {'usdt_total': 0, 'usdt_free': 0},
            'open_positions': [],
            'current_price': 0,
            'total_notional': 0,
            'total_pnl': 0,
            'total_pnl_pct': 0,
            'daily_trades': 0,
            'daily_winning': 0,
            'daily_pnl_pct': 0,
            'strategy_running': False,
            'strategy_pid': None,
            'error': None
        }
        
        try:
            # 加载市场
            exchange.load_markets()
            
            # 检查余额
            balance = exchange.fetch_balance()
            usdt_total = balance['USDT']['total'] if 'USDT' in balance else 0
            usdt_free = balance['USDT']['free'] if 'USDT' in balance else 0
            
            instance_report['balance'] = {
                'usdt_total': usdt_total,
                'usdt_free': usdt_free
            }
            
            # 检查持仓
            positions = exchange.fetch_positions([symbol])
            open_positions = [p for p in positions if float(p.get('contracts', 0)) != 0]
            
            # 获取当前价格
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            instance_report['current_price'] = current_price
            
            # 分析当日绩效
            total_trades, winning_trades, total_pnl_percent = analyze_daily_performance_for_instance(workspace_path)
            instance_report['daily_trades'] = total_trades
            instance_report['daily_winning'] = winning_trades
            instance_report['daily_pnl_pct'] = total_pnl_percent
            
            for pos in open_positions:
                contracts = float(pos.get('contracts', 0))
                notional = float(pos.get('notional', 0))
                entry_price = float(pos.get('entryPrice', 0))
                pnl = float(pos.get('unrealizedPnl', 0))
                pnl_pct = (pnl / notional * 100) if notional > 0 else 0
                
                instance_report['total_notional'] += notional
                instance_report['total_pnl'] += pnl
                
                position_info = {
                    'direction': 'long' if pos['side'] == 'long' else 'short',
                    'contracts': contracts,
                    'notional': notional,
                    'entry_price': entry_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct
                }
                instance_report['open_positions'].append(position_info)
            
            if instance_report['total_notional'] > 0:
                instance_report['total_pnl_pct'] = (instance_report['total_pnl'] / instance_report['total_notional'] * 100)
            
            # 检查策略运行状态
            try:
                strategy_running = False
                strategy_pid = None
                
                # 方法1：检查PID文件
                pid_file = "strategy_pid.txt"
                if os.path.exists(pid_file):
                    try:
                        with open(pid_file, 'r') as f:
                            pid = int(f.read().strip())
                        if os.path.exists(f"/proc/{pid}"):
                            cmdline_file = f"/proc/{pid}/cmdline"
                            if os.path.exists(cmdline_file):
                                with open(cmdline_file, 'r') as f:
                                    cmdline = f.read()
                                    if "okx_doomsday_fixed.py" in cmdline:
                                        strategy_running = True
                                        strategy_pid = pid
                    except:
                        pass
                
                # 方法2：使用ps命令
                if not strategy_running:
                    ps_output = subprocess.check_output(["ps", "aux"]).decode()
                    for line in ps_output.split('\n'):
                        if "okx_doomsday_fixed.py" in line and "grep" not in line and "/usr/bin/bash -c" not in line:
                            parts = line.split()
                            if len(parts) > 1:
                                try:
                                    pid = int(parts[1])
                                    # 进一步验证这是否属于这个实例
                                    # 检查进程的工作目录
                                    try:
                                        cwd_link = f"/proc/{pid}/cwd"
                                        if os.path.exists(cwd_link):
                                            actual_cwd = os.readlink(cwd_link)
                                            if actual_cwd == os.getcwd() or actual_cwd == workspace_path:
                                                strategy_running = True
                                                strategy_pid = pid
                                    except:
                                        # 如果无法检查cwd，则假设它是
                                        strategy_running = True
                                        strategy_pid = pid
                                        break
                                except:
                                    continue
                
                instance_report['strategy_running'] = strategy_running
                instance_report['strategy_pid'] = strategy_pid
                
            except Exception as e:
                instance_report['error'] = f"策略状态检查失败: {str(e)}"
            
        except Exception as e:
            instance_report['error'] = str(e)
        
        os.chdir(original_cwd)
        return instance_report
        
    except Exception as e:
        print(f"❌ 处理实例 {instance_name} 时出错: {e}")
        os.chdir(original_cwd)
        return None

def generate_multi_currency_report():
    """生成多币种汇总报告"""
    base_path = "/root/.openclaw/workspace"
    instances = [
        ("freqtrade_workspace", "ETH"),
        ("freqtrade_workspace_btc", "BTC"),
        ("freqtrade_workspace_sol", "SOL"),
        ("freqtrade_workspace_okb", "DOGE")  # 原OKB，现改为DOGE
    ]
    
    all_reports = []
    report_lines = []
    
    report_lines.append("📊 **多币种持仓汇总报告**")
    report_lines.append(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    
    total_usdt = 0
    total_notional_all = 0
    total_pnl_all = 0
    total_daily_trades = 0
    total_daily_winning = 0
    
    for folder, name in instances:
        workspace_path = os.path.join(base_path, folder)
        if not os.path.exists(workspace_path):
            continue
            
        print(f"📈 处理 {name} 实例...")
        instance_report = get_instance_position_report(workspace_path, name)
        
        if instance_report is None:
            continue
            
        all_reports.append(instance_report)
        
        # 汇总数据
        total_usdt += instance_report['balance']['usdt_total']
        total_notional_all += instance_report['total_notional']
        total_pnl_all += instance_report['total_pnl']
        total_daily_trades += instance_report['daily_trades']
        total_daily_winning += instance_report['daily_winning']
        
        # 为每个实例生成报告部分
        report_lines.append(f"---")
        report_lines.append(f"💰 **{name} ({instance_report['symbol']})**")
        
        if instance_report.get('error'):
            report_lines.append(f"❌ 错误: {instance_report['error']}")
            continue
        
        # 余额信息
        usdt_total = instance_report['balance']['usdt_total']
        usdt_free = instance_report['balance']['usdt_free']
        report_lines.append(f"  余额: ${usdt_total:.2f} (可用: ${usdt_free:.2f})")
        report_lines.append(f"  当前价格: ${instance_report['current_price']:.2f}")
        
        # 持仓信息
        if instance_report['open_positions']:
            report_lines.append(f"  持仓数量: {len(instance_report['open_positions'])}")
            for pos in instance_report['open_positions']:
                direction = "做多" if pos['direction'] == 'long' else "做空"
                report_lines.append(f"  {direction}: {pos['contracts']}合约, 价值: ${pos['notional']:.2f}")
                report_lines.append(f"    均价: ${pos['entry_price']:.2f}, 盈亏: ${pos['pnl']:.2f} ({pos['pnl_pct']:+.2f}%)")
            
            report_lines.append(f"  持仓总计: ${instance_report['total_notional']:.2f}")
            report_lines.append(f"  总盈亏: ${instance_report['total_pnl']:.2f} ({instance_report['total_pnl_pct']:+.2f}%)")
            if usdt_total > 0:
                position_pct = (instance_report['total_notional'] / usdt_total * 100)
                report_lines.append(f"  仓位占比: {position_pct:.1f}%")
        else:
            report_lines.append("  ✅ 无持仓")
        
        # 当日绩效
        if instance_report['daily_trades'] > 0:
            win_rate = (instance_report['daily_winning'] / instance_report['daily_trades'] * 100) if instance_report['daily_trades'] > 0 else 0
            report_lines.append(f"  今日交易: {instance_report['daily_trades']}次, 盈利: {instance_report['daily_winning']}次")
            report_lines.append(f"  胜率: {win_rate:.1f}%, 累计盈亏: {instance_report['daily_pnl_pct']:+.2f}%")
        else:
            report_lines.append("  今日交易: 0次")
        
        # 策略状态
        if instance_report['strategy_running']:
            report_lines.append(f"  策略状态: 🟢 运行中 (PID: {instance_report['strategy_pid']})")
        else:
            report_lines.append("  策略状态: 🔴 未运行")
    
    # 生成汇总部分
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("📊 **所有实例汇总**")
    report_lines.append(f"💰 总余额: ${total_usdt:.2f}")
    
    if total_notional_all > 0:
        total_pnl_pct_all = (total_pnl_all / total_notional_all * 100) if total_notional_all > 0 else 0
        report_lines.append(f"📈 总持仓价值: ${total_notional_all:.2f}")
        report_lines.append(f"📊 总未实现盈亏: ${total_pnl_all:.2f} ({total_pnl_pct_all:+.2f}%)")
        if total_usdt > 0:
            total_position_pct = (total_notional_all / total_usdt * 100)
            report_lines.append(f"⚖️  总仓位占比: {total_position_pct:.1f}%")
    
    if total_daily_trades > 0:
        total_win_rate = (total_daily_winning / total_daily_trades * 100) if total_daily_trades > 0 else 0
        report_lines.append(f"📅 今日总交易: {total_daily_trades}次")
        report_lines.append(f"🏆 总胜率: {total_win_rate:.1f}%")
    
    # 活跃实例统计
    active_count = sum(1 for r in all_reports if r.get('strategy_running', False))
    total_count = len(all_reports)
    report_lines.append(f"🔄 活跃实例: {active_count}/{total_count}")
    
    # 实例概览表
    report_lines.append("")
    report_lines.append("📋 **实例概览**")
    report_lines.append("币种 | 余额 | 持仓 | 盈亏 | 今日交易 | 状态")
    report_lines.append("---|---|---|---|---|---")
    
    for report in all_reports:
        name = report['name']
        usdt_total = report['balance']['usdt_total']
        has_position = "有" if report['open_positions'] else "无"
        pnl_display = f"${report['total_pnl']:+.2f}" if report['total_pnl'] != 0 else "-"
        daily_trades = f"{report['daily_trades']}次" if report['daily_trades'] > 0 else "无"
        status = "🟢" if report.get('strategy_running', False) else "🔴"
        
        report_lines.append(f"{name} | ${usdt_total:.0f} | {has_position} | {pnl_display} | {daily_trades} | {status}")
    
    report_lines.append("")
    report_lines.append("---")
    report_lines.append(f"🔄 下次报告: 1小时后 ({datetime.now().hour + 1}:00)")
    
    return "\n".join(report_lines)

def send_to_feishu(message):
    """通过OpenClaw发送消息到Feishu"""
    try:
        # 用户ID
        user_id = "ou_a371832abcd231155817dbf6d4d5d931"
        
        # 构建命令 - 使用node直接执行openclaw脚本，避免env问题
        cmd = [
            "/root/.nvm/versions/node/v22.22.0/bin/node",
            "/root/.nvm/versions/node/v22.22.0/bin/openclaw", "message", "send",
            "--channel", "feishu",
            "--target", f"user:{user_id}",
            "--message", message
        ]
        
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ 多币种持仓报告发送成功")
            return True
        else:
            print(f"❌ 发送失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 发送异常: {e}")
        return False

def main():
    """主函数"""
    print(f"📊 生成多币种持仓报告: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 生成报告
    report = generate_multi_currency_report()
    
    # 打印报告（用于调试）
    print(report)
    
    # 发送到Feishu
    print("\n📤 发送报告到Feishu...")
    success = send_to_feishu(report)
    
    if success:
        print("🎉 多币种报告发送完成")
    else:
        print("⚠️  报告发送失败，请检查配置")

if __name__ == "__main__":
    main()