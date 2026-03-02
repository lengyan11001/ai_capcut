# 双 OpenClaw 部署：学习实例仅管理员 + 用户实例独立资源

本文档说明如何部署「主实例（带学习能力）」与「用户实例」双 Gateway，并在平台侧配置学习白名单与路由。推荐使用**实例池自动分配**：先配置一批用户实例，用户注册时自动绑定其中一个。单实例部署见 [OPENCLAW_SERVER_SETUP.md](OPENCLAW_SERVER_SETUP.md)。

## 一、架构简述

- **主实例（学习）**：端口 18789，单 agent（如 `main`），支持 `clawhub install` / 学习；**仅平台配置的白名单账号**会走此实例。
- **用户实例**：端口 18790（或其它），可一机多实例；**非白名单用户**走用户实例。推荐实例池模式：每个用户绑定一个实例，默认 `agent_id=main`。
- **平台**：根据当前登录用户是否在白名单内，选择调用主实例或用户实例及对应 agent。

## 二、主实例（学习）- 保持现有

- 端口：**18789**（或你当前端口）。
- 配置：沿用现有 `~/.openclaw/openclaw.json`，单 agent、workspace 如 `~/.openclaw/workspace`，无需改为多 agent。
- 谁能用：由平台 `.env` 中的 **OPENCLAW_LEARN_ALLOWLIST** 控制（见下文「平台配置」）。

## 三、用户实例（新建）

### 3.1 独立配置与状态目录

与主实例隔离，任选其一：

**方式 A：环境变量指定状态目录（同机第二份配置）**

```bash
export OPENCLAW_STATE_DIR=~/.openclaw-users
export OPENCLAW_CONFIG_PATH=~/.openclaw-users/openclaw.json
```

创建目录并写入用户实例配置：

```bash
mkdir -p ~/.openclaw-users
```

**方式 B：单独安装目录**

将 OpenClaw 安装到另一目录，或用不同 profile，通过 `OPENCLAW_CONFIG_PATH` 指向 `~/.openclaw-users/openclaw.json`。

### 3.2 用户实例 openclaw.json 示例（实例池模式，默认 agent=main）

路径：`~/.openclaw-users/openclaw.json`（或你选的 `OPENCLAW_CONFIG_PATH`）。

```json5
{
  "gateway": {
    "mode": "local",
    "port": 18790,
    "bind": "127.0.0.1",
    "auth": {
      "mode": "token",
      "token": "请替换为与主实例不同的强随机 token"
    },
    "http": {
      "endpoints": {
        "chatCompletions": { "enabled": true }
      }
    }
  },
  "agent": {
    "workspace": "~/.openclaw-users/workspace-main"
  },
  "mcp": {
    "servers": {
      "ai-test-platform": { "url": "http://127.0.0.1:8001/mcp" }
    }
  }
}
```

- 该示例为「每实例默认 main agent」：实例池分配时给用户绑定 `agent_id=main`，由“一个用户一个实例”实现隔离。
- 若你想一个实例服务多个用户，可改用多 agent 模式（下节）。

### 3.3 可选：多 agent 模式（单实例服务多个用户）

若你不采用实例池（一个用户一个实例），而是单个用户实例里做多 agent，OpenClaw 无动态创建 agent 的 API，需在服务器上**预先或按需**执行：

1. 在 `agents.list` 中追加一项，例如 `{ "id": "user_3", "workspace": "~/.openclaw-users/workspace-user_3" }`。
2. 创建目录并初始化 workspace：
   ```bash
   mkdir -p ~/.openclaw-users/workspace-user_3
   OPENCLAW_CONFIG_PATH=~/.openclaw-users/openclaw.json openclaw setup --workspace ~/.openclaw-users/workspace-user_3
   ```
   注意：需在**用户实例**使用的配置环境下执行（即 `OPENCLAW_CONFIG_PATH=~/.openclaw-users/openclaw.json` 或等效）。
3. 重启用户实例 Gateway，使新 agent 生效。

**脚本**：在仓库中执行 `OPENCLAW_STATE_DIR=~/.openclaw-users OPENCLAW_CONFIG_PATH=~/.openclaw-users/openclaw.json ./scripts/add-openclaw-user-agent.sh <平台_user_id>` 可自动创建 workspace 并提示在 `agents.list` 中追加条目；若已安装 jq 可据此检查是否已存在。完成后需重启用户实例 Gateway。

### 3.4 实例池自动分配（推荐）

平台已支持实例池：

- 注册用户后自动从可用实例池中分配一个实例并绑定（按 `current_users` 最少优先）。
- 若实例设置了 `max_users` 且已满，不会再分配。
- 聊天时优先按用户绑定路由到该实例（而不是全体共用 `OPENCLAW_GATEWAY_URL_USERS`）。

管理端 API（需 `X-Admin-Token`）：

- `GET /auth/openclaw-instances`：查看实例池
- `POST /auth/openclaw-instances`：新增实例
- `PUT /auth/openclaw-instances/{instance_id}`：更新实例
- `GET /auth/openclaw-bindings`：查看用户绑定
- `POST /auth/openclaw-bindings/assign/{user_id}`：为存量用户手动触发分配

示例：新增一台用户实例

```bash
curl -X POST "http://127.0.0.1:8000/auth/openclaw-instances" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: 你的ADMIN_SECRET" \
  -d '{
    "name":"user-gw-01",
    "base_url":"http://127.0.0.1:28790",
    "gateway_token":"对应实例token",
    "default_agent_id":"main",
    "max_users":50,
    "enabled":true
  }'
```

### 3.5 启动用户实例

```bash
OPENCLAW_STATE_DIR=~/.openclaw-users OPENCLAW_CONFIG_PATH=~/.openclaw-users/openclaw.json openclaw gateway --port 18790
```

或使用 systemd：新建 `openclaw-gateway-users.service`，在 `Environment` 与 `ExecStart` 中写上上述环境变量与 `--port 18790`。

## 四、平台配置（.env）

在 ai_test_platform 的 `.env` 中配置双实例与白名单：

```env
# 学习实例（主实例，仅白名单使用）
OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789
OPENCLAW_GATEWAY_TOKEN=主实例的token

# 用户实例（多 agent）
OPENCLAW_GATEWAY_URL_USERS=http://127.0.0.1:18790
OPENCLAW_GATEWAY_TOKEN_USERS=用户实例的token

# 学习实例白名单：逗号分隔的 user id 或 email，仅这些账号走主实例
OPENCLAW_LEARN_ALLOWLIST=1
# 或按邮箱：OPENCLAW_LEARN_ALLOWLIST=admin@example.com
# 或多个：OPENCLAW_LEARN_ALLOWLIST=1,2,admin@example.com
```

- 若**不配置** `OPENCLAW_GATEWAY_URL_USERS` / `OPENCLAW_GATEWAY_TOKEN_USERS`：所有人仍走单一 Gateway（当前 `OPENCLAW_GATEWAY_URL`），与之前行为一致。
- 若配置了用户实例：白名单内用户走主实例（学习），其余用户优先走实例池绑定；无绑定时回退到 `OPENCLAW_GATEWAY_URL_USERS`（兼容模式）。

## 五、Skill 同步（主实例 → 用户实例，可选）

主实例通过 `clawhub install` 学到的 skill 可同步到用户实例，供所有使用用户实例的 agent 使用。

### 5.1 共享目录与 extraDirs

1. 在服务器上建共享目录，例如：
   ```bash
   sudo mkdir -p /var/openclaw/shared-skills
   sudo chown 你的用户:你的用户 /var/openclaw/shared-skills
   ```
2. 在**用户实例**的 `openclaw.json` 中增加：
   ```json5
   "skills": {
     "load": {
       "extraDirs": ["/var/openclaw/shared-skills"]
     }
   }
   ```
3. 重启用户实例使配置生效。

### 5.2 同步脚本（rsync）

使用仓库内脚本（需在 ai_test_platform 或项目根执行）：

```bash
chmod +x scripts/sync-openclaw-skills.sh
./scripts/sync-openclaw-skills.sh
```

默认从 `~/.openclaw/workspace/skills` 同步到 `/var/openclaw/shared-skills`。可通过环境变量覆盖：

- `OPENCLAW_LEARN_SKILLS_DIR`：主实例 skill 目录（默认 `~/.openclaw/workspace/skills`）
- `OPENCLAW_SHARED_SKILLS_DIR`：共享目录（默认 `/var/openclaw/shared-skills`）

可按需在脚本内加入白名单，只同步允许对用户开放的 skill 子集。建议 cron 定期执行或主实例安装 skill 后手动执行。

## 六、可选：Skill 封装为 MCP 并按用户开放

若需要「只对部分用户开放某 skill」或「用户实例不同步某 skill 但通过 MCP 提供」：

- 在平台 MCP（或后端）中为选定的 skill 能力新增 MCP tool，handler 内根据调用方用户校验权限后再转发到主实例或后端实现。
- 权限数据可在平台 DB 或配置中维护（用户 – 可用 skill/tool 列表）。  
具体设计与实现可在「同步方案上线后确有按用户开放需求」时再做，此处仅作规划说明。

## 七、参考

- 单实例安装与 Chat Completions： [OPENCLAW_SERVER_SETUP.md](OPENCLAW_SERVER_SETUP.md)
- OpenClaw 多 agent：[Multi-Agent Routing](https://docs.openclaw.ai/concepts/multi-agent)
- 本平台 MCP： [MCP_SETUP.md](MCP_SETUP.md)
