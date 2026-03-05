# OpenClaw 控制台

OpenClaw 控制台：聚合与管理已接入的工具与服务，提供登录、积分计费、智能对话等能力；并包含 testAI（API 测试/用例生成）等技能入口。

## 功能概览

- **用户与积分**：注册、登录、JWT 鉴权，剩余积分查询（`/auth/me`）
- **单接口测试**：`POST /api-test`，传入 URL、Method、Body 等，执行一次 HTTP 请求并返回结果（扣 1 积分/次）
- **从文档生成并执行**：`POST /api-test/from-doc`，传入 Swagger/OpenAPI 文档地址，自动解析生成用例并可选执行（执行按 1 积分/条）
- **计费规则**：`GET /auth/pricing` 公开查看
- **前端**：根路径 `/` 提供登录/注册页与简易控制台（积分、跳转 API 文档）

## 项目结构

```text
ai_test_platform/
  ├── README.md
  ├── requirements.txt
  ├── .env.example          # 环境变量示例，复制为 .env
  ├── Dockerfile
  ├── docker-compose.yml
  ├── static/
  │   └── index.html        # 登录/注册/控制台
  ├── docs/
  │   └── MCP_AND_COST.md   # MCP 工具清单与成本核算
  └── backend/
      └── app/
          ├── main.py
          ├── __init__.py   # FastAPI 应用、CORS、静态资源挂载
          ├── db.py
          ├── models.py
          ├── api/
          │   ├── health.py
          │   ├── auth.py   # 注册/登录/me/pricing
          │   ├── chat.py
          │   └── api_test.py
          └── core/
              ├── config.py
              └── credits.py
```

## 本地运行

### 1. 依赖与环境变量

```bash
cd ai_test_platform
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # 按需修改 SECRET_KEY、CORS_ORIGINS 等
```

### 2. 启动服务

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

浏览器访问：

- 首页（登录/注册/控制台）：http://localhost:8000/
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

### 3. 环境变量说明（.env）

| 变量 | 说明 | 默认 |
|------|------|------|
| SECRET_KEY | JWT 签名密钥，生产必改 | 见 .env.example |
| DEBUG | 是否输出 500 详细错误 | true |
| CORS_ORIGINS | 允许的跨域来源，逗号分隔 | localhost:8000 |
| DATABASE_URL | 数据库连接（本地可省略，用 SQLite） | sqlite:///./ai_test_platform.db |

## Docker 一键部署

在项目根目录（ai_test_platform）下执行：

```bash
# 构建并启动（数据持久化在 volume app_data）
docker compose up -d --build

# 查看日志
docker compose logs -f app
```

首次部署建议设置生产用密钥（可选）：

```bash
export SECRET_KEY=$(openssl rand -hex 32)
export DEBUG=false
docker compose up -d --build
```

访问：http://localhost:8000/ （若宿主机端口未改）。

### 常用命令

```bash
docker compose down      # 停止并删除容器
docker compose up -d     # 后台启动
docker compose ps        # 查看状态
```

数据保存在 Docker volume `app_data`，删除容器不会丢失用户与积分数据（除非执行 `docker compose down -v`）。

## 部署到服务器

**详细说明**（服务器选型、规格建议、一步步操作、Nginx + HTTPS）：见 [docs/DEPLOY.md](docs/DEPLOY.md)。

简要步骤：

1. 将本仓库拉到服务器（或仅 `ai_test_platform` 目录）。
2. 在 `ai_test_platform` 下执行：
   - `cp .env.example .env`，编辑 `.env` 设置 `SECRET_KEY`、`DEBUG=false`、`CORS_ORIGINS`（含前端实际域名）。
   - `docker compose up -d --build`。
3. 如需对外域名：在 Nginx/Caddy 中反向代理 `http://127.0.0.1:8000`，并保证 `CORS_ORIGINS` 包含该域名。
4. 如需 HTTPS：在反向代理层配置证书即可（详见 DEPLOY.md）。

## 成本与计费

详见 [docs/MCP_AND_COST.md](docs/MCP_AND_COST.md)：积分单价、套餐建议、固定成本与盈亏平衡估算。

## 群控系统（Reddit POC）

已支持一期群控最小闭环：

- 云端控制面：设备心跳、任务创建/取消、Agent 拉取任务、执行结果与日志回传
- 本地执行面：`local_agent` 主动连云端，不暴露 ADB 公网端口
- 自动化驱动：先接入 Reddit POC（Appium + UiAutomator2）

文档见：

- [docs/GROUP_CONTROL.md](docs/GROUP_CONTROL.md)
- [local_agent/README.md](local_agent/README.md)

## 能力目录（白名单路由）

平台 MCP 服务支持通过能力目录文件管理可用能力，避免在系统提示词中堆叠大量工具说明。

- 目录文件：`mcp/capability_catalog.json`
- 本地覆盖（推荐运维修改）：`mcp/capability_catalog.local.json`（未纳入 git，MCP 启动时优先读取）
- 关键字段：
  - `description`：能力描述（面向 Agent）
  - `upstream`：上游服务名（如 `sutui`）
  - `upstream_tool`：上游 MCP 工具名
  - `enabled`：是否启用
- 环境变量：
  - `CAPABILITY_CATALOG_PATH`：可选，覆盖默认目录文件路径
  - `CAPABILITY_UPSTREAM_URLS_JSON`：上游映射 JSON，例如 `{"sutui":"https://xxx/mcp-http?api_key=***"}`
  - `CAPABILITY_ALLOWLIST`：能力白名单（逗号分隔）

建议将上述环境变量配置在 `ai-test-platform-mcp.service`（MCP 服务）中，而不是后端 API 服务。

### 避免 git pull 冲突（强烈建议）

- 不要在服务器直接修改受版本控制的 `mcp/capability_catalog.json`。
- 运维改能力时优先编辑 `mcp/capability_catalog.local.json`（本地覆盖文件，不进 git）。
- 若需更彻底隔离，使用 systemd 环境变量 `CAPABILITY_CATALOG_PATH=/etc/ai-test-platform/capability_catalog.json` 指向仓库外文件。

### 能力管理与审计 API

- 用户态：
  - `GET /capabilities/available`：查询当前用户可用能力（已做策略过滤）
  - `POST /capabilities/record-call`：记录能力调用审计并按规则扣费
- 管理态（需 `X-Admin-Token`）：
  - `GET /capabilities/registry` / `POST /capabilities/registry` / `PUT /capabilities/registry/{capability_id}`
  - `GET /capabilities/policies` / `POST /capabilities/policies` / `PUT /capabilities/policies/{policy_id}`
  - `GET /capabilities/call-logs`

### 部署流程（能力封装版）

1. 更新代码并重启后端（自动建表 + 首次导入 `mcp/capability_catalog.json`）：
   - `docker compose up -d --build app`
2. 为 MCP 服务配置上游映射（systemd）：
   - `CAPABILITY_UPSTREAM_URLS_JSON={"sutui":"https://.../mcp-http?api_key=..."}`
   - 可选：`CAPABILITY_ALLOWLIST=image.generate,task.get_result`
3. 重启 MCP 服务：
   - `sudo systemctl daemon-reload`
   - `sudo systemctl restart ai-test-platform-mcp.service`
4. 在管理端写入能力计费与策略：
   - 将 `unit_credits` 配置为每次调用扣费
   - 通过策略接口按 `user_id/email` 做 allow/deny
5. 联调验证：
   - 用户调用 `list_capabilities` 仅看到授权能力
   - `invoke_capability` 成功后，`/capabilities/call-logs` 可看到审计，`/auth/credit-flows` 可看到扣费流水
