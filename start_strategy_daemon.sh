#!/bin/bash
# 策略守护进程脚本（增强版）
# 自动重启策略进程，确保持续运行，支持飞书通知

WORKDIR="/root/.openclaw/workspace/freqtrade_workspace_btc"
LOG_DIR="$WORKDIR/logs"
STRATEGY_PID_FILE="$WORKDIR/strategy_pid.txt"
MONITOR_LOG="$LOG_DIR/strategy_monitor_btc.log"
STRATEGY_SCRIPT="okx_doomsday_fixed.py"

# 飞书通知配置
FEISHU_USER_ID="ou_a371832abcd231155817dbf6d4d5d931"
OPENCLAW_PATH="/root/.nvm/versions/node/v22.22.0/bin/openclaw"
NOTIFICATION_COOLDOWN_SECONDS=300  # 5分钟冷却时间，避免频繁通知
LAST_NOTIFICATION_TIME=0

# 创建日志目录
mkdir -p "$LOG_DIR"

# 日志函数
log_monitor() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$MONITOR_LOG"
}

# 发送飞书通知
send_feishu_notification() {
    local message="$1"
    local current_time=$(date +%s)
    
    # 冷却时间检查（避免频繁通知）
    if [ $((current_time - LAST_NOTIFICATION_TIME)) -lt $NOTIFICATION_COOLDOWN_SECONDS ]; then
        log_monitor "跳过飞书通知（冷却时间中）: $message"
        return 0
    fi
    
    log_monitor "发送飞书通知: $message"
    
    # 使用openclaw发送飞书消息
    if [ -f "$OPENCLAW_PATH" ]; then
        "$OPENCLAW_PATH" message send \
            --channel feishu \
            --target "$FEISHU_USER_ID" \
            --message "$message" \
            >> "$LOG_DIR/feishu_notification_btc.log" 2>&1 &
        LAST_NOTIFICATION_TIME=$current_time
        log_monitor "飞书通知已发送"
    else
        log_monitor "错误: openclaw路径不存在: $OPENCLAW_PATH"
    fi
}

# 检查策略进程是否运行
check_strategy() {
    if [ -f "$STRATEGY_PID_FILE" ]; then
        PID=$(cat "$STRATEGY_PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0  # 进程存在
        else
            log_monitor "进程 $PID 不存在，策略可能已停止"
            return 1
        fi
    else
        log_monitor "PID文件不存在"
        return 1
    fi
}

# 启动策略
start_strategy() {
    log_monitor "正在启动策略..."
    
    # 使用虚拟环境Python
    cd "$WORKDIR"
    nohup .venv/bin/python "$STRATEGY_SCRIPT" > "$LOG_DIR/current_strategy_btc.log" 2>&1 &
    NEW_PID=$!
    
    echo "$NEW_PID" > "$STRATEGY_PID_FILE"
    sleep 3
    
    # 检查是否启动成功
    if ps -p "$NEW_PID" > /dev/null 2>&1; then
        log_monitor "策略启动成功，PID: $NEW_PID"
        send_feishu_notification "✅ 策略重启成功 (PID: $NEW_PID)"
        return 0
    else
        log_monitor "策略启动失败，请检查日志"
        send_feishu_notification "❌ 策略启动失败，请检查日志"
        return 1
    fi
}

# 主循环
log_monitor "=== 策略守护进程启动 ==="
send_feishu_notification "🔄 策略守护进程启动，开始监控"

while true; do
    if ! check_strategy; then
        log_monitor "检测到策略停止，尝试重启..."
        send_feishu_notification "⚠️ 检测到策略停止，正在尝试重启..."
        start_strategy
        if [ $? -ne 0 ]; then
            log_monitor "重启失败，等待30秒后重试"
            # 重启失败通知已在start_strategy中发送
            sleep 30
        fi
    else
        # 策略正常运行，等待1分钟再检查
        sleep 60
    fi
done