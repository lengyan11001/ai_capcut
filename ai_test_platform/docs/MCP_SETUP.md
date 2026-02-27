# MCP Server 配置与使用

测试平台通过 MCP（Model Context Protocol）暴露工具，供 Cursor 等客户端调用：单接口测试、从 OpenAPI 文档生成/执行用例、查积分与计费。

## 一、环境要求

- **Python 3.10+**（MCP SDK 要求，若本机只有 3.9 可单独建 3.10 虚拟环境或使用 uv/pyenv）
- 依赖：`mcp`、`httpx`（见 `mcp/requirements.txt`）

## 二、安装依赖

在项目根目录（`ai_test_platform`）下执行：

```bash
pip install -r mcp/requirements.txt
```

或进入 `mcp` 目录后：

```bash
cd mcp && pip install -r requirements.txt
```

## 三、环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `AI_TEST_PLATFORM_BASE_URL` | 测试平台后端地址 | `http://localhost:8000` 或 `https://your-domain.com` |
| `AI_TEST_PLATFORM_TOKEN` | 登录后获取的 Bearer token（调用需扣费接口时必填） | 在平台登录后从接口或前端获取 |

## 四、本地运行（stdio，供 Cursor 连接）

在 **`ai_test_platform`** 目录下执行：

```bash
export AI_TEST_PLATFORM_BASE_URL=http://localhost:8000
export AI_TEST_PLATFORM_TOKEN=你的token
python -m mcp
```

进程会以 stdio 方式等待 MCP 客户端连接，无输出时正常。Ctrl+C 退出。

## 五、Cursor 配置

1. 打开 Cursor 的 MCP 配置（如 Settings → MCP，或项目下 `.cursor/mcp.json`）。
2. 新增一条 Server，例如：

**方式一：stdio（推荐，本地或远程后端）**

```json
{
  "mcpServers": {
    "ai-test-platform": {
      "command": "python",
      "args": ["-m", "mcp"],
      "cwd": "/绝对路径/ai_test_platform",
      "env": {
        "AI_TEST_PLATFORM_BASE_URL": "http://localhost:8000",
        "AI_TEST_PLATFORM_TOKEN": "你的登录token"
      }
    }
  }
}
```

- `cwd` 请改为你本机的 `ai_test_platform` 绝对路径。
- 若后端部署在别的机器，将 `AI_TEST_PLATFORM_BASE_URL` 改为该地址；token 仍为在平台登录后获取的 token。

**方式二：HTTP（仅 URL，需服务端先起 MCP HTTP 服务）**

若已在某台机器上以 HTTP 模式运行 MCP（见第七节），在 Cursor 中只需配置 url，token 放在 query：

```json
{
  "mcpServers": {
    "ai-test-platform": {
      "url": "http://服务器IP:8001/mcp?token=你的平台token"
    }
  }
}
```

**方式三：使用 uv（stdio）**

若已安装 uv，可将 `command` 改为 `uv`，`args` 改为 `["run", "python", "-m", "mcp"]`，并保证 `cwd` 指向 `ai_test_platform`（含 `mcp/` 与可选 `pyproject.toml` 的目录）。

## 六、暴露的工具

| 工具名 | 说明 | 扣费 |
|--------|------|------|
| `run_api_test` | 执行单次 HTTP 接口测试 | 1 积分/次 |
| `generate_cases_from_doc` | 仅从文档生成用例，不执行 | 0 |
| `generate_and_run_from_doc` | 从文档生成并执行用例 | 按执行条数 × 1 积分 |
| `get_me` | 当前用户信息与剩余积分 | 0 |
| `list_pricing` | 计费规则（积分单价） | 0 |

详见 [MCP_AND_COST.md](MCP_AND_COST.md)。

## 七、HTTP 模式（独立端口，token 走 query）

若希望像速推一样「只填一个 URL」、无需配置 cwd/command/env，可在服务器上以 **HTTP 模式** 跑 MCP，Cursor 端用 `url` + query 传 token。

### 7.1 启动 HTTP MCP 服务

在 **仓库根目录**（`ai_capcut`，即 `ai_test_platform` 的上一级）下，设置后端地址后启动（默认端口 8001）：

```bash
cd /path/to/ai_capcut
export AI_TEST_PLATFORM_BASE_URL=http://你的平台域名或IP:8000
python -m ai_test_platform.mcp --http
```

指定端口：

```bash
python -m ai_test_platform.mcp --http --port 8002
```

服务根路径为 `/mcp`，例如：`http://服务器IP:8001/mcp`。

### 7.2 Cursor 配置（仅 URL）

在 Cursor 的 MCP 配置中新增一条，**只填 url**，token 放在 query 里：

```json
{
  "mcpServers": {
    "ai-test-platform": {
      "url": "http://你的服务器IP:8001/mcp?token=你的平台登录token"
    }
  }
}
```

- 将 `你的服务器IP`、`8001`（若改过端口则对应修改）、`你的平台登录token` 替换为实际值。
- 前端控制台「复制 Token」拿到 token 后，拼到 `?token=` 后面即可；无需再配 cwd、command、env。

### 7.3 部署到服务器

1. 在服务器上进入仓库根目录，安装 MCP 依赖：`pip install -r ai_test_platform/mcp/requirements.txt`。
2. 设置环境变量 `AI_TEST_PLATFORM_BASE_URL` 指向平台后端（如 `http://127.0.0.1:8000` 若与后端同机）。
3. 常驻运行：`python -m ai_test_platform.mcp --http --port 8001`（可用 systemd/supervisor）；放通 8001 端口或 Nginx 反代。
4. 用户在 Cursor 中只配置上述 `url` 即可。
