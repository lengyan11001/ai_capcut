#!/usr/bin/env bash
# 为平台用户在 OpenClaw 用户实例中新增一个 agent 及其 workspace。
# 用法: ./add-openclaw-user-agent.sh <平台 user_id>
# 依赖: 用户实例配置已存在，OPENCLAW_CONFIG_PATH 或 OPENCLAW_STATE_DIR 指向用户实例；
#       openclaw 在 PATH 中；jq 可选（用于自动写 agents.list）。
# 示例: OPENCLAW_STATE_DIR=~/.openclaw-users OPENCLAW_CONFIG_PATH=~/.openclaw-users/openclaw.json ./add-openclaw-user-agent.sh 3

set -e
USER_ID="${1:?用法: $0 <平台 user_id>}"
AGENT_ID="user_${USER_ID}"
STATE_DIR="${OPENCLAW_STATE_DIR:-$HOME/.openclaw-users}"
CONFIG_PATH="${OPENCLAW_CONFIG_PATH:-$STATE_DIR/openclaw.json}"
WORKSPACE_DIR="$STATE_DIR/workspace-$AGENT_ID"

echo "Agent ID: $AGENT_ID"
echo "Workspace: $WORKSPACE_DIR"
echo "Config: $CONFIG_PATH"

mkdir -p "$WORKSPACE_DIR"
if command -v openclaw &>/dev/null; then
  OPENCLAW_CONFIG_PATH="$CONFIG_PATH" openclaw setup --workspace "$WORKSPACE_DIR"
  echo "Workspace 已初始化。"
else
  echo "未找到 openclaw 命令，请手动执行: openclaw setup --workspace $WORKSPACE_DIR"
fi

if [ -f "$CONFIG_PATH" ] && command -v jq &>/dev/null; then
  if ! jq -e --arg id "$AGENT_ID" '.agents.list[] | select(.id == $id)' "$CONFIG_PATH" &>/dev/null; then
    echo "请手动在 $CONFIG_PATH 的 agents.list 中追加: {\"id\": \"$AGENT_ID\", \"workspace\": \"$WORKSPACE_DIR\"}"
    echo "然后重启用户实例 Gateway。"
  else
    echo "agents.list 中已存在 $AGENT_ID。请重启用户实例 Gateway 使新 workspace 生效。"
  fi
else
  echo "请手动在配置的 agents.list 中追加: {\"id\": \"$AGENT_ID\", \"workspace\": \"$WORKSPACE_DIR\"}"
  echo "然后重启用户实例 Gateway。"
fi
