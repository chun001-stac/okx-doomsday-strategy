#!/bin/bash
# 多实例Git同步脚本
# 自动提交所有策略实例的改动到git仓库

set -e

# 工作目录列表
INSTANCES=(
    "/root/.openclaw/workspace/freqtrade_workspace"      # ETH
    "/root/.openclaw/workspace/freqtrade_workspace_btc"  # BTC
    "/root/.openclaw/workspace/freqtrade_workspace_sol"  # SOL
)

LOG_FILE="/root/.openclaw/workspace/freqtrade_workspace/git_sync_multi.log"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "开始多实例Git同步流程..."
log "共有 ${#INSTANCES[@]} 个实例需要同步"

TOTAL_COMMITS=0
TOTAL_SUCCESS=0

for INSTANCE_DIR in "${INSTANCES[@]}"; do
    INSTANCE_NAME=$(basename "$INSTANCE_DIR")
    
    log ""
    log "=== 处理实例: $INSTANCE_NAME ($INSTANCE_DIR) ==="
    
    # 检查目录是否存在
    if [ ! -d "$INSTANCE_DIR" ]; then
        log "❌ 错误: 目录不存在, 跳过"
        continue
    fi
    
    # 进入工作目录
    cd "$INSTANCE_DIR"
    
    # 检查git是否已初始化
    if [ ! -d ".git" ]; then
        log "⚠️ 警告: Git仓库未初始化, 跳过"
        continue
    fi
    
    # 检查是否有远程仓库配置
    REMOTE_COUNT=$(git remote -v | wc -l)
    if [ "$REMOTE_COUNT" -eq 0 ]; then
        log "ℹ️ 信息: 未配置远程仓库，仅进行本地提交"
        REMOTE_EXISTS=false
    else
        REMOTE_EXISTS=true
        log "✅ 检测到远程仓库配置"
    fi
    
    # 检查是否有未提交的更改
    CHANGED_FILES=$(git status --porcelain)
    if [ -n "$CHANGED_FILES" ]; then
        log "📝 检测到未提交的更改"
        
        # 获取更改的文件列表（排除.gitignore文件）
        FILE_LIST=$(echo "$CHANGED_FILES" | grep -v '^.gitignore$' | awk '{print $2}' | grep -v '^$' | tr '\n' ', ')
        
        if [ -z "$FILE_LIST" ]; then
            log "ℹ️  只有.gitignore文件更改，跳过提交"
            continue
        fi
        
        # 添加所有更改的文件（排除敏感文件）
        git add -A
        
        # 创建提交消息
        COMMIT_MSG="策略更新 $(date '+%Y-%m-%d %H:%M:%S')
        
实例: $INSTANCE_NAME
更改的文件: $FILE_LIST
自动提交于: $(date)"

        # 提交更改
        if git commit -m "$COMMIT_MSG"; then
            log "✅ 已提交更改: $FILE_LIST"
            TOTAL_COMMITS=$((TOTAL_COMMITS + 1))
            
            # 如果有远程仓库，则推送
            if [ "$REMOTE_EXISTS" = true ]; then
                log "🔄 正在推送到远程仓库..."
                if git push; then
                    log "✅ 推送成功"
                    TOTAL_SUCCESS=$((TOTAL_SUCCESS + 1))
                else
                    log "⚠️ 警告: 推送失败，但提交已保存到本地"
                fi
            else
                log "ℹ️ 未配置远程仓库，提交仅保存到本地"
            fi
            
            # 显示提交统计
            COMMIT_COUNT=$(git rev-list --count HEAD 2>/dev/null || echo "未知")
            log "📊 当前提交总数: $COMMIT_COUNT"
            
        else
            log "❌ 提交失败"
        fi
        
    else
        log "ℹ️ 没有检测到更改，跳过提交"
    fi
done

log ""
log "=== 同步完成 ==="
log "总提交次数: $TOTAL_COMMITS"
log "推送成功次数: $TOTAL_SUCCESS"
log "多实例Git同步流程完成"
echo "" >> "$LOG_FILE"