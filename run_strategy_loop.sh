#!/bin/bash
# 策略循环运行脚本
# 如果策略异常退出，自动重启

WORKDIR="/root/.openclaw/workspace/freqtrade_workspace"
LOG_DIR="$WORKDIR/logs"
STRATEGY_SCRIPT="okx_doomsday_fixed.py"
RESTART_DELAY=10  # 重启延迟（秒）
LOOP_LOG="$LOG_DIR/strategy_loop.log"

cd "$WORKDIR"

log_loop() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOOP_LOG"
}

log_loop "=== 策略循环启动 ==="

while true; do
    # 生成带时间戳的日志文件名
    TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
    STRATEGY_LOG="$LOG_DIR/strategy_${TIMESTAMP}.log"
    
    log_loop "启动策略，日志: $STRATEGY_LOG"
    
    # 运行策略（前台运行）
    .venv/bin/python "$STRATEGY_SCRIPT" > "$STRATEGY_LOG" 2>&1
    
    EXIT_CODE=$?
    log_loop "策略退出，退出码: $EXIT_CODE"
    
    # 检查退出码，如果是正常退出（如Ctrl+C）则停止循环
    if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 130 ]; then
        log_loop "策略正常退出，停止循环"
        break
    fi
    
    # 异常退出，等待后重启
    log_loop "等待 ${RESTART_DELAY} 秒后重启..."
    sleep $RESTART_DELAY
done

log_loop "策略循环结束"