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

**方式二：使用 uv**

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

## 七、部署到一台机器（可选）

若希望多人共用同一 MCP 端点，可将 MCP 以 **streamable-http** 方式跑在一台服务器上：

1. 在服务器上安装依赖并设置 `AI_TEST_PLATFORM_BASE_URL`、`AI_TEST_PLATFORM_TOKEN`。
2. 启动时使用 HTTP 传输，例如在 `mcp/__main__.py` 中改为 `mcp.run(transport="streamable-http")`（具体以 MCP SDK 文档为准），并指定 host/port。
3. 使用 systemd、supervisor 或 Docker 常驻运行该进程。
4. 在 Cursor 中配置 MCP 为「HTTP/SSE」连接，填写该服务器 URL。

当前默认为 **stdio**，适合本机 Cursor 直连；部署为 HTTP 时再按需修改启动方式与 Cursor 配置。
