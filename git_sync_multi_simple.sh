#!/bin/bash
# 多实例Git同步脚本（简化安全版本）
# 自动提交所有策略实例的改动

set -e

# 工作目录列表
INSTANCES=(
    "/root/.openclaw/workspace/freqtrade_workspace"      # ETH
    "/root/.openclaw/workspace/freqtrade_workspace_btc"  # BTC
    "/root/.openclaw/workspace/freqtrade_workspace_sol"  # SOL
    "/root/.openclaw/workspace/freqtrade_workspace_okb"  # DOGE (原OKB，现改为DOGE)
)

LOG_FILE="/root/.openclaw/workspace/freqtrade_workspace/git_sync_multi.log"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# GitHub配置（从环境变量读取令牌）
GITHUB_REPO="chun001-stac/okx-doomsday-strategy"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

if [ -n "$GITHUB_TOKEN" ]; then
    GITHUB_URL="https://${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git"
    log "✅ 检测到GitHub令牌，将推送到远程仓库"
else
    GITHUB_URL="https://github.com/${GITHUB_REPO}.git"
    log "⚠️ 未检测到GitHub令牌，仅进行本地提交"
fi

# 检查并更新git版本
check_and_update_git() {
    log "=== Git版本检查 ==="
    CURRENT_VERSION=$(git --version | awk '{print $3}')
    log "当前Git版本: $CURRENT_VERSION"
}

# 配置Git用户信息
setup_git_user() {
    if [ -z "$(git config user.email)" ]; then
        git config user.email "trader@okx-simulation.com"
    fi
    if [ -z "$(git config user.name)" ]; then
        git config user.name "OKX Simulation Trader"
    fi
}

# 配置GitHub远程仓库（仅ETH实例）
setup_github_remote() {
    INSTANCE_NAME=$1
    
    # 只配置ETH实例到GitHub
    if [ "$INSTANCE_NAME" != "freqtrade_workspace" ]; then
        return 0
    fi
    
    # 如果没有令牌，不配置远程仓库
    if [ -z "$GITHUB_TOKEN" ]; then
        return 0
    fi
    
    # 检查是否已有远程仓库
    if git remote -v | grep -q "github.com"; then
        return 0
    fi
    
    git remote remove origin 2>/dev/null || true
    git remote add origin "$GITHUB_URL" 2>/dev/null && log "✅ 已配置GitHub远程仓库"
}

log "开始多实例Git同步流程..."
log "GitHub令牌状态: $([ -n "$GITHUB_TOKEN" ] && echo "已配置" || echo "未配置")"

check_and_update_git

TOTAL_COMMITS=0
TOTAL_SUCCESS=0

for INSTANCE_DIR in "${INSTANCES[@]}"; do
    INSTANCE_NAME=$(basename "$INSTANCE_DIR")
    
    log ""
    log "=== 处理实例: $INSTANCE_NAME ==="
    
    if [ ! -d "$INSTANCE_DIR" ] || [ ! -d "$INSTANCE_DIR/.git" ]; then
        log "跳过: 目录或Git仓库不存在"
        continue
    fi
    
    cd "$INSTANCE_DIR"
    
    setup_git_user
    setup_github_remote "$INSTANCE_NAME"
    
    # 检查是否有远程仓库
    if git remote -v | grep -q "github.com"; then
        REMOTE_EXISTS=true
        log "已连接远程仓库"
    else
        REMOTE_EXISTS=false
        log "仅本地提交"
    fi
    
    # 检查未提交的更改
    CHANGED_FILES=$(git status --porcelain)
    if [ -z "$CHANGED_FILES" ]; then
        log "没有更改，跳过"
        continue
    fi
    
    # 提交更改
    git add -A
    if git commit -m "策略更新 $(date '+%Y-%m-%d %H:%M:%S') - $INSTANCE_NAME"; then
        log "✅ 已提交更改"
        TOTAL_COMMITS=$((TOTAL_COMMITS + 1))
        
        # 推送到GitHub（仅ETH实例且有令牌）
        if [ "$REMOTE_EXISTS" = true ] && [ "$INSTANCE_NAME" = "freqtrade_workspace" ] && [ -n "$GITHUB_TOKEN" ]; then
            if git push origin main 2>/dev/null || git push --force-with-lease origin main 2>/dev/null; then
                log "✅ GitHub推送成功"
                TOTAL_SUCCESS=$((TOTAL_SUCCESS + 1))
            else
                log "⚠️ GitHub推送失败"
            fi
        fi
    fi
done

log ""
log "=== 同步完成 ==="
log "总提交: $TOTAL_COMMITS, 成功推送: $TOTAL_SUCCESS"