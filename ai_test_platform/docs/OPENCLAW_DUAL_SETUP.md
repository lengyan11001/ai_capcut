# 双 OpenClaw 部署：管理员一套 + 普通用户一套（完全隔离）

本文档说明如何在服务器上跑**两套相互独立的** OpenClaw Gateway：一套等价于以前「单实例给管理员用」，另一套专门给所有普通用户。平台用 `OPENCLAW_LEARN_ALLOWLIST` 区分账号走哪套。推荐使用**实例池**给用户分配用户侧实例。单实例部署见 [OPENCLAW_SERVER_SETUP.md](OPENCLAW_SERVER_SETUP.md)。

## 一、架构简述

- **管理员实例**（`OPENCLAW_GATEWAY_URL`，如 18789）：与旧单实例一致，仅 **白名单** 内账号的智能对话会打到这台；`/learn`、skill、workspace 都在这套 OpenClaw 里。
- **用户实例**（`OPENCLAW_GATEWAY_URL_USERS` 或实例池，如 18790）：**所有非白名单**账号只走这里，与管理员实例进程、状态目录、workspace 完全分开。
- **平台**：先看是否在白名单 → 是则只连管理员实例；否则只连用户侧（绑定实例池或回退 `OPENCLAW_GATEWAY_URL_USERS`），**不会**把普通用户请求打到管理员那台。

## 二、管理员实例（原单实例）- 保持现有

- 端口：**18789**（或你当前端口）。
- 配置：沿用现有 `~/.openclaw/openclaw.json`，单 agent、workspace 如 `~/.openclaw/workspace`，无需改为多 agent。
- 谁能用：`.env` 里 **OPENCLAW_LEARN_ALLOWLIST** 中的 user id 或 email（见下文「平台配置」）。

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
# 管理员专用 OpenClaw（原单实例）
OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789
OPENCLAW_GATEWAY_TOKEN=管理员实例的token

# 普通用户专用 OpenClaw（全新独立实例）
OPENCLAW_GATEWAY_URL_USERS=http://127.0.0.1:18790
OPENCLAW_GATEWAY_TOKEN_USERS=用户实例的token

# 仅以下账号走 OPENCLAW_GATEWAY_URL（管理员），其余账号只走用户侧
OPENCLAW_LEARN_ALLOWLIST=1
# 或按邮箱：OPENCLAW_LEARN_ALLOWLIST=admin@example.com
# 或多个：OPENCLAW_LEARN_ALLOWLIST=1,2,admin@example.com

# 极少用：true 时强制白名单也走用户实例（排障）
# OPENCLAW_LEARN_ALLOWLIST_USE_USERS_GATEWAY=
```

- 若**不配置** `OPENCLAW_GATEWAY_URL_USERS` / `OPENCLAW_GATEWAY_TOKEN_USERS`：所有人仍走单一 Gateway（`OPENCLAW_GATEWAY_URL`），与旧版单实例一致。
- 若配置了用户实例：**白名单 → 管理员实例**；**非白名单 → 实例池或 `OPENCLAW_GATEWAY_URL_USERS`**，两套流量完全分开。

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
