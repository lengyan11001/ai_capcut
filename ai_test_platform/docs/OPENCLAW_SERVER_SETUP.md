# OpenClaw 服务器安装与配置

本文档说明在服务器上安装并配置 OpenClaw Gateway，使「智能对话」能通过会话理解用户意图并调用 MCP（接口测试、用例生成等）。

## 一、服务器要求

- **系统**：Linux（推荐 Ubuntu 22.04+）或 WSL2
- **配置**：建议 2 核 2G 内存以上；仅跑 Gateway + 远程模型 API，不跑本地大模型时可 2G
- **Node.js**：22.12.0 及以上（OpenClaw 要求）
- **已部署**：本平台后端（FastAPI）与前端；MCP 服务（如本平台 HTTP MCP、速推等）可同机或远程

## 二、安装 OpenClaw

### 2.1 安装 Node.js 22+

若未安装或版本过低：

```bash
# 使用 nvm（推荐）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc   # 或 ~/.zshrc
nvm install 22
nvm use 22

# 或 Ubuntu 使用 NodeSource
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
```

验证：

```bash
node -v   # 应 >= v22.12.0
npm -v
```

### 2.2 安装 OpenClaw

任选其一。

**方式 A：官方一键脚本（会安装 Node 若缺失）**

```bash
curl -fsSL https://openclaw.ai/install.sh | bash
```

**方式 B：npm 全局安装**

```bash
npm install -g openclaw@latest
```

验证：

```bash
openclaw --version
openclaw doctor   # 可选，检查环境
```

## 三、配置文件

OpenClaw 配置使用 JSON5，路径一般为 `~/.openclaw/openclaw.json`。若目录不存在可先创建：

```bash
mkdir -p ~/.openclaw
```

### 3.1 最小可用配置（仅 Gateway + Chat Completions + MCP）

创建或编辑 `~/.openclaw/openclaw.json`，内容示例（按需修改）：

```json5
{
  "agent": {
    "workspace": "~/.openclaw/workspace"
  },
  "gateway": {
    "mode": "local",
    "port": 18789,
    "bind": "127.0.0.1",
    "auth": {
      "mode": "token",
      "token": "请替换为强随机字符串"
    },
    "http": {
      "endpoints": {
        "chatCompletions": { "enabled": true }
      }
    }
  },
  "mcp": {
    "servers": {
      "ai-test-platform": {
        "url": "http://127.0.0.1:8001/mcp",
        "env": {}
      }
    }
  }
}
```

说明：

- **gateway.port**：Gateway 监听端口，默认 18789；与后端同机时可用 127.0.0.1，仅本机访问。
- **gateway.auth.token**：鉴权 token，后端代理请求 OpenClaw 时使用同一 token；请改为随机字符串（如 `openssl rand -hex 32`）。
- **gateway.http.endpoints.chatCompletions.enabled**：必须为 `true`，否则无法使用 Chat Completions 接口。
- **mcp.servers**：登记 MCP 服务。`ai-test-platform` 示例为同机 HTTP MCP（端口 8001）；若 MCP 需带用户 token，见下方「MCP 与用户鉴权」。

### 3.2 MCP 与用户鉴权（可选）

若希望 OpenClaw 调用「本平台 MCP」时按当前登录用户扣费，需在调用 MCP 时带上该用户的 JWT。当前 OpenClaw 配置中无法按请求动态注入用户 token，可选用以下方式之一：

- **方式一**：MCP 使用固定「服务端账号」token，扣费由后端在调用 OpenClaw 前后按用户单独扣减（在业务层实现）。
- **方式二**：本平台 MCP 支持从 URL 参数或 Header 读取 token；若未来 OpenClaw 支持在 Chat Completions 请求中传递自定义 header/参数并注入到 MCP，可在彼时再配置。

同机 MCP 若需在 URL 中带 token（例如平台 JWT），可把 `url` 写成：

```json5
"url": "http://127.0.0.1:8001/mcp?token=平台服务端或测试用JWT"
```

注意：此处为静态 token，无法按前端用户区分。

### 3.3 增加其他 MCP（如速推）

在 `mcp.servers` 中继续添加即可，例如：

```json5
"mcp": {
  "servers": {
    "ai-test-platform": { "url": "http://127.0.0.1:8001/mcp" },
    "速推AI": {
      "url": "https://ts-api.fyshark.com/api/v3/mcp-http?api_key=你的api_key"
    }
  }
}
```

保存后需重启 Gateway 生效。

## 四、启动 OpenClaw Gateway

### 4.1 前台运行（调试用）

```bash
openclaw gateway
```

默认监听 `127.0.0.1:18789`。Ctrl+C 退出。

### 4.2 指定端口与绑定地址

```bash
openclaw gateway --port 18789
```

若需对外暴露（不推荐无鉴权暴露），可在配置中修改 `gateway.bind` 或使用 `--bind`（以官方文档为准），并务必保留 `gateway.auth.token`。

### 4.3 使用 systemd 常驻（推荐生产）

创建 unit 文件：

```bash
sudo tee /etc/systemd/system/openclaw-gateway.service << 'EOF'
[Unit]
Description=OpenClaw Gateway
After=network.target

[Service]
Type=simple
User=你的运行用户
WorkingDirectory=/home/你的用户
Environment="PATH=/usr/bin:/usr/local/bin:你的node路径"
ExecStart=/usr/bin/openclaw gateway
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

将 `ExecStart` 中的 `/usr/bin/openclaw` 改为实际 `which openclaw` 路径；`User`、`WorkingDirectory` 改为实际用户与目录。若使用 nvm，可改为：

```ini
Environment="PATH=/home/你的用户/.nvm/versions/node/v22.x.x/bin:..."
ExecStart=/home/你的用户/.nvm/versions/node/v22.x.x/bin/openclaw gateway
```

然后：

```bash
sudo systemctl daemon-reload
sudo systemctl enable openclaw-gateway
sudo systemctl start openclaw-gateway
sudo systemctl status openclaw-gateway
```

日志查看：`journalctl -u openclaw-gateway -f`。

## 五、本平台后端配置

在 **ai_test_platform** 的 `.env` 中增加（与 `~/.openclaw/openclaw.json` 中 `gateway.auth.token` 一致）：

```env
OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789
OPENCLAW_GATEWAY_TOKEN=你在 openclaw.json 里配置的 token
```

若 Gateway 与后端不在同机，将 `OPENCLAW_GATEWAY_URL` 改为实际地址（如 `http://内网IP:18789`）。保存后重启本平台后端。

## 六、MCP 服务与本平台同机时的端口

- 本平台 **后端**：默认 8000（uvicorn）
- 本平台 **HTTP MCP**：若按文档单独起在 8001，则 `mcp.servers["ai-test-platform"].url` 为 `http://127.0.0.1:8001/mcp`；若 MCP 挂在后端同一进程则用 8000 对应路径（以实际部署为准）
- **OpenClaw Gateway**：18789

确保防火墙或安全组放行本机 8000/8001/18789（仅本机访问时可只绑定 127.0.0.1，不对外暴露）。

## 七、验证

1. **Gateway 是否在监听**

   ```bash
   curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18789/
   ```
   有响应即可（不一定是 200）。

2. **Chat Completions 是否可用**

   ```bash
   curl -s -X POST http://127.0.0.1:18789/v1/chat/completions \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer 你的gateway_token" \
     -H "x-openclaw-agent-id: main" \
     -d '{"model":"openclaw","messages":[{"role":"user","content":"hi"}]}'
   ```
   应返回 JSON，内含 `choices` 或错误信息；若 401 则检查 token。

3. **前端**  
   登录平台 → 控制台 → 「智能对话」tab → 输入一条消息发送。若配置正确，应收到 OpenClaw 的回复；若未配置或 Gateway 未起，会看到占位提示或 502/503。

## 八、常见问题

- **502 / 无法连接 OpenClaw Gateway**  
  检查：Gateway 是否已启动；`OPENCLAW_GATEWAY_URL` 是否与 Gateway 监听地址一致；本机防火墙是否拦截。

- **401 Unauthorized**  
  `.env` 中的 `OPENCLAW_GATEWAY_TOKEN` 必须与 `~/.openclaw/openclaw.json` 中 `gateway.auth.token` 完全一致。

- **OpenClaw 不调用 MCP**  
  确认 `mcp.servers` 中对应服务可访问（如本机 `curl` 该 URL）；OpenClaw 需配置大模型（如 Claude/OpenAI API）才能推理并决定是否调工具，请在 OpenClaw 官方文档中配置 `agent.model` 及相应 API 密钥。

- **2G 内存是否够用**  
  仅跑 Gateway + 远程模型时一般够用；不要在本机再跑本地大模型（如 Ollama）。可限制 worker 数量（如 uvicorn `--workers 1`）。

## 九、参考链接

- [OpenClaw Gateway 文档](https://docs.openclaw.ai/cli/gateway)
- [OpenClaw 配置参考](https://docs.openclaw.ai/gateway/configuration-reference)
- [使用 Chat Completions 接口](https://open-claw.bot/docs/api/gateway/)
- 本平台 MCP：见 [MCP_SETUP.md](MCP_SETUP.md)
