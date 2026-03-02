#!/usr/bin/env bash
# 将主实例（学习）的 skill 目录同步到用户实例使用的共享目录。
# 用法: ./sync-openclaw-skills.sh
# 可选环境变量:
#   OPENCLAW_LEARN_SKILLS_DIR  主实例 skill 目录，默认 ~/.openclaw/workspace/skills
#   OPENCLAW_SHARED_SKILLS_DIR 共享目录（用户实例 extraDirs），默认 /var/openclaw/shared-skills
# 需对两目录有读写权限；建议 cron 定期执行或主实例安装 skill 后手动执行。

set -e
LEARN_SKILLS="${OPENCLAW_LEARN_SKILLS_DIR:-$HOME/.openclaw/workspace/skills}"
SHARED_SKILLS="${OPENCLAW_SHARED_SKILLS_DIR:-/var/openclaw/shared-skills}"

if [ ! -d "$LEARN_SKILLS" ]; then
  echo "主实例 skill 目录不存在: $LEARN_SKILLS"
  echo "可设置 OPENCLAW_LEARN_SKILLS_DIR 指向实际路径（如 ~/.openclaw/skills）。"
  exit 1
fi

mkdir -p "$SHARED_SKILLS"
rsync -av --delete "$LEARN_SKILLS/" "$SHARED_SKILLS/"
echo "已同步 $LEARN_SKILLS -> $SHARED_SKILLS"
