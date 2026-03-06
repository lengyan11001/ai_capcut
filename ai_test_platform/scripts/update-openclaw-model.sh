#!/usr/bin/env bash
# update-openclaw-model.sh
# 将 OpenClaw Gateway 的后端模型从直连 DeepSeek 切换为 ephone.chat 代理
# 用法: bash scripts/update-openclaw-model.sh
# 会自动备份原配置，修改后需重启 openclaw-gateway

set -euo pipefail

OPENCLAW_CONFIG="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}"

if [ ! -f "$OPENCLAW_CONFIG" ]; then
  echo "❌ 找不到 OpenClaw 配置文件: $OPENCLAW_CONFIG"
  echo "   如果配置在其他位置，请设置 OPENCLAW_CONFIG_PATH 环境变量"
  exit 1
fi

echo "📝 OpenClaw 配置文件: $OPENCLAW_CONFIG"

# 备份
BACKUP="${OPENCLAW_CONFIG}.bak.$(date +%Y%m%d%H%M%S)"
cp "$OPENCLAW_CONFIG" "$BACKUP"
echo "💾 已备份到: $BACKUP"

if ! command -v python3 &>/dev/null; then
  echo "❌ 需要 python3 来解析 JSON"
  exit 1
fi

python3 << 'PYEOF'
import json, sys, os, re

config_path = os.environ.get("OPENCLAW_CONFIG_PATH", os.path.expanduser("~/.openclaw/openclaw.json"))

with open(config_path, "r") as f:
    raw = f.read()
    # json5 简单兼容：去掉行注释
    clean = re.sub(r'//.*$', '', raw, flags=re.MULTILINE)
    # 去掉尾逗号
    clean = re.sub(r',\s*([\]}])', r'\1', clean)
    config = json.loads(clean)

EPHONE_BASE = "https://api.ephone.chat/v1"
EPHONE_KEY = "sk-grBrNrmOhzjPuiJxm4aAbxmFg2gshPabpYIvzDk3FDxg7Ews"

# 确保 models.providers 存在
if "models" not in config:
    config["models"] = {}
if "providers" not in config["models"]:
    config["models"]["providers"] = {}

providers = config["models"]["providers"]

# 添加 ephone-deepseek 作为 provider
providers["ephone-deepseek"] = {
    "baseUrl": EPHONE_BASE,
    "headers": {
        "Authorization": f"Bearer {EPHONE_KEY}"
    }
}

# 如果已有 openai-compatible 指向 deepseek.com，保留为 deepseek-direct
if "openai-compatible" in providers:
    existing_url = providers["openai-compatible"].get("baseUrl", "")
    if "deepseek.com" in existing_url:
        providers["deepseek-direct"] = providers.pop("openai-compatible")
        print(f"  ➡️  原 openai-compatible (deepseek.com) 改名为 deepseek-direct")

# 设置 agents.defaults.model 使用 ephone，原 deepseek 作为 fallback
if "agents" not in config:
    config["agents"] = {}
if "defaults" not in config["agents"]:
    config["agents"]["defaults"] = {}

current_model = config["agents"]["defaults"].get("model", {})
if isinstance(current_model, str):
    current_model = {"primary": current_model}
elif not isinstance(current_model, dict):
    current_model = {}

old_primary = current_model.get("primary", "")

# 新的主模型用 ephone-deepseek
current_model["primary"] = "ephone-deepseek/deepseek-chat"

# 把原来的模型放到 fallbacks
fallbacks = current_model.get("fallbacks", [])
if old_primary and old_primary != "ephone-deepseek/deepseek-chat":
    if old_primary not in fallbacks:
        fallbacks.insert(0, old_primary)
# 确保 deepseek-direct 在 fallbacks
if "deepseek-direct" in providers:
    ds_fb = "deepseek-direct/deepseek-chat"
    if ds_fb not in fallbacks:
        fallbacks.append(ds_fb)
if fallbacks:
    current_model["fallbacks"] = fallbacks

config["agents"]["defaults"]["model"] = current_model

# 确保 env 里有 key（部分 OpenClaw 版本需要）
if "env" not in config:
    config["env"] = {}
config["env"]["EPHONE_API_KEY"] = EPHONE_KEY

with open(config_path, "w") as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print(f"\n✅ 已更新 OpenClaw 配置:")
print(f"   主模型: {current_model['primary']}")
if current_model.get("fallbacks"):
    print(f"   备选: {', '.join(current_model['fallbacks'])}")
print(f"   ephone endpoint: {EPHONE_BASE}")
PYEOF

echo ""
echo "📌 下一步："
echo "   sudo systemctl restart openclaw-gateway"
echo "   # 或重启用户实例："
echo "   # sudo systemctl restart openclaw-gateway-users"
