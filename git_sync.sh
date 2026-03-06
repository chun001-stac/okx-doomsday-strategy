#!/bin/bash
# 每日Git同步脚本
# 自动提交策略改动到git仓库

set -e

# 工作目录
WORKDIR="/root/.openclaw/workspace/freqtrade_workspace"
LOG_FILE="$WORKDIR/git_sync.log"

# 进入工作目录
cd "$WORKDIR"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "开始Git同步流程..."

# 检查git是否已初始化
if [ ! -d ".git" ]; then
    log "错误: Git仓库未初始化"
    exit 1
fi

# 检查是否有远程仓库配置
REMOTE_COUNT=$(git remote -v | wc -l)
if [ "$REMOTE_COUNT" -eq 0 ]; then
    log "警告: 未配置远程仓库，仅进行本地提交"
    REMOTE_EXISTS=false
else
    REMOTE_EXISTS=true
    log "检测到远程仓库配置"
fi

# 检查是否有未提交的更改
if git status --porcelain | grep -q '^[ MARC][ MD]'; then
    log "检测到未提交的更改"
    
    # 添加所有更改的文件
    git add -A
    
    # 获取更改的文件列表
    CHANGED_FILES=$(git status --porcelain | awk '{print $2}' | tr '\n' ', ')
    
    # 创建提交消息
    COMMIT_MSG="策略更新 $(date '+%Y-%m-%d %H:%M:%S')
    
更改的文件: $CHANGED_FILES
自动提交于: $(date)"

    # 提交更改
    git commit -m "$COMMIT_MSG"
    log "已提交更改: $CHANGED_FILES"
    
    # 如果有远程仓库，则推送
    if [ "$REMOTE_EXISTS" = true ]; then
        log "正在推送到远程仓库..."
        if git push; then
            log "推送成功"
        else
            log "警告: 推送失败，但提交已保存到本地"
        fi
    else
        log "未配置远程仓库，提交仅保存到本地"
    fi
    
    # 显示提交统计
    COMMIT_COUNT=$(git rev-list --count HEAD)
    log "当前提交总数: $COMMIT_COUNT"
    
else
    log "没有检测到更改，跳过提交"
fi

log "Git同步流程完成"
echo "" >> "$LOG_FILE"