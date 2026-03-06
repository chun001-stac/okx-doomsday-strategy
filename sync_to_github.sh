#!/bin/bash
# GitHub同步脚本（新结构）
# 自动提交策略代码更新到GitHub主分支

set -e

# 工作目录
WORKDIR="/root/.openclaw/workspace/okx-strategy"
LOG_FILE="$WORKDIR/sync_to_github.log"

# GitHub配置（从环境变量读取令牌）
GITHUB_REPO="chun001-stac/okx-doomsday-strategy"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

if [ -n "$GITHUB_TOKEN" ]; then
    GITHUB_URL="https://${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 检测到GitHub令牌，将推送到远程仓库" | tee -a "$LOG_FILE"
else
    GITHUB_URL="https://github.com/${GITHUB_REPO}.git"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️ 未检测到GitHub令牌，仅进行本地提交" | tee -a "$LOG_FILE"
fi

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== 开始GitHub同步流程 ==="

cd "$WORKDIR"

# 配置Git用户信息（如果未配置）
if [ -z "$(git config user.email)" ]; then
    git config user.email "trader@okx-simulation.com"
    log "配置Git邮箱: trader@okx-simulation.com"
fi

if [ -z "$(git config user.name)" ]; then
    git config user.name "OKX Simulation Trader"
    log "配置Git用户名: OKX Simulation Trader"
fi

# 检查是否有远程仓库配置
if ! git remote -v | grep -q "github.com"; then
    log "配置GitHub远程仓库..."
    git remote remove origin 2>/dev/null || true
    if git remote add origin "$GITHUB_URL"; then
        log "✅ 已配置GitHub远程仓库"
    else
        log "❌ 配置GitHub远程仓库失败"
        exit 1
    fi
fi

# 拉取最新代码（避免冲突）
log "🔄 正在拉取远程最新代码..."
if git pull --rebase origin main; then
    log "✅ 拉取最新代码成功"
else
    log "⚠️ 拉取最新代码失败，继续本地操作"
fi

# 检查是否有未提交的更改
CHANGED_FILES=$(git status --porcelain)
if [ -z "$CHANGED_FILES" ]; then
    log "ℹ️ 没有检测到更改，跳过提交"
    exit 0
fi

# 显示更改的文件
log "📝 检测到未提交的更改:"
echo "$CHANGED_FILES" | while read line; do
    log "  $line"
done

# 添加所有更改的文件
git add -A

# 创建提交消息
COMMIT_MSG="策略代码更新 $(date '+%Y-%m-%d %H:%M:%S')

更改的文件:
$(echo "$CHANGED_FILES" | awk '{print "  - " $2}' | sort)"

if git commit -m "$COMMIT_MSG"; then
    log "✅ 已提交更改"
    
    # 推送到GitHub（如果有令牌）
    if [ -n "$GITHUB_TOKEN" ]; then
        log "🔄 正在推送到GitHub仓库..."
        if git push origin main; then
            log "✅ GitHub推送成功 (分支: main)"
        else
            log "⚠️ 首次推送失败，尝试强制推送..."
            if git push --force-with-lease origin main; then
                log "✅ GitHub强制推送成功 (分支: main)"
            else
                log "❌ GitHub推送失败，但提交已保存到本地"
                log "ℹ️ 可能的原因：令牌权限不足、网络问题或分支冲突"
            fi
        fi
    else
        log "ℹ️ 无GitHub令牌，提交仅保存到本地"
    fi
else
    log "❌ 提交失败"
fi

log "=== 同步完成 ==="