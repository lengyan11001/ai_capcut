# 服务器选型与部署步骤

本文给出测试平台后端 + 可选 Nginx/HTTPS 的服务器推荐与具体操作步骤。MCP 推荐在**用户本机**以 stdio 方式运行，仅需将 `AI_TEST_PLATFORM_BASE_URL` 指向你部署的后端地址。

---

## 一、服务器推荐

### 1.1 规格建议

| 场景 | 配置建议 | 说明 |
|------|----------|------|
| 个人 / 体验 | 1 核 2G，20～40G 系统盘 | 跑 Docker 单容器 + SQLite 足够 |
| 小团队（&lt; 20 人） | 2 核 4G，40G 系统盘 | 可长期用 SQLite；并发高再考虑 RDS |
| 小团队 + 预留扩展 | 2 核 4G，+ 独立 RDS/MySQL | 数据库与应用分离，便于备份与扩容 |

当前应用无状态，仅 SQLite 存用户与积分；无 AI 时 CPU/内存占用很低，1 核 2G 即可稳定跑。

### 1.2 云厂商与产品

- **国内**
  - **阿里云**：轻量应用服务器（约 ￥24/月起）或 ECS 按量/包月
  - **腾讯云**：轻量应用服务器（约 ￥24/月起）或云服务器 CVM
  - **华为云**：弹性云服务器 ECS
- **海外**（若用户多在海外或需国际访问）
  - **DigitalOcean**：Droplet 约 $6/月起（1 核 1G）
  - **Vultr**：Cloud Compute 约 $6/月起
  - **AWS Lightsail**：约 $5/月起

选**同一地域**（如团队在华东选华东节点），系统盘 20G 以上即可。

### 1.3 系统与端口

- **系统**：推荐 **Ubuntu 22.04 LTS**（或 20.04），便于装 Docker 与 Nginx。
- **端口**：开放 **22**（SSH）、**80**（HTTP）、**443**（HTTPS）；若暂不用 Nginx 直连应用，可再开放 **8000**（仅测试用，生产建议用 Nginx 反代）。

---

## 二、部署方式概览

- **推荐**：Docker + docker compose 一键起后端，数据持久化在 volume。
- **可选**：同一台机用 Nginx 做反向代理并配 HTTPS（域名 + 证书）。

MCP 不部署到服务器：每个用户在**本机**运行 `python -m mcp`（stdio），Cursor 里把 `AI_TEST_PLATFORM_BASE_URL` 指到你部署好的后端地址即可。

---

## 三、具体操作步骤（Docker 部署）

### 3.1 购买并登录服务器

1. 在云控制台购买一台云服务器（规格见上一节），系统选 Ubuntu 22.04。
2. 安全组/防火墙放通：22、80、443（及可选 8000）。
3. 使用 SSH 登录，例如：
   ```bash
   ssh root@你的服务器公网IP
   ```
   （若使用密钥，则 `ssh -i 你的密钥.pem root@IP`。）

### 3.2 安装 Docker 与 Docker Compose

```bash
# 更新并安装 Docker（Ubuntu）
apt update && apt install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 确认
docker --version && docker compose version
```

### 3.3 上传代码并配置环境变量

**方式 A：git 克隆（推荐）**

```bash
cd /opt
git clone 你的仓库地址 ai_test_platform
cd ai_test_platform
# 若仓库根目录不是 ai_test_platform，则进入包含 backend/、static/、docker-compose.yml 的目录
```

**方式 B：本地上传**

在本机打包（不含 `.venv`、`.env`）后上传到服务器，例如 `/opt/ai_test_platform`，并解压。

**配置 .env：**

```bash
cd /opt/ai_test_platform
cp .env.example .env
nano .env   # 或 vi .env
```

至少修改：

- `SECRET_KEY`：生产环境必改，可用 `openssl rand -hex 32` 生成。
- `DEBUG=false`。
- `CORS_ORIGINS`：填前端实际访问的域名，例如 `https://api.your-domain.com,https://your-domain.com`（多个用英文逗号分隔）。

保存退出。

### 3.4 构建并启动容器

```bash
cd /opt/ai_test_platform
docker compose up -d --build
```

查看是否运行正常：

```bash
docker compose ps
curl -s http://127.0.0.1:8000/health
```

应返回健康检查结果。此时本机可通过 `http://服务器IP:8000` 访问（若 8000 已放通）。

### 3.5 配置 Nginx 反向代理（可选）

若要用域名 + 80/443 访问，在同一台机安装 Nginx 并反代到 8000：

```bash
apt install -y nginx
```

新建站点配置，例如：

```bash
nano /etc/nginx/sites-available/ai-test-platform
```

内容示例（替换 `your-domain.com` 为你的域名）：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用并重载：

```bash
ln -s /etc/nginx/sites-available/ai-test-platform /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

浏览器访问 `http://your-domain.com` 应能打开平台。`.env` 中 `CORS_ORIGINS` 需包含该域名（如 `https://your-domain.com`）。

### 3.6 配置 HTTPS（可选）

使用 Let’s Encrypt 免费证书（需域名已解析到该服务器）：

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d your-domain.com
```

按提示选择即可，证书会自动续期。之后用 `https://your-domain.com` 访问，`CORS_ORIGINS` 中改为 `https://your-domain.com`。

---

## 四、MCP 使用方式（不部署 MCP 到服务器）

- **后端**：按上面步骤部署后，对外地址为 `https://your-domain.com` 或 `http://服务器IP:8000`。
- **MCP**：在**每位用户的电脑**上运行（Cursor 通过 stdio 调用本机进程）：
  1. 安装 Python 3.10+ 与依赖：`pip install -r mcp/requirements.txt`（在 `ai_test_platform` 目录下）。
  2. 设置环境变量：`AI_TEST_PLATFORM_BASE_URL=https://your-domain.com`，`AI_TEST_PLATFORM_TOKEN=用户登录后获取的 token`。
  3. 在 Cursor 的 MCP 配置中，添加该 Server，`cwd` 指向本机 `ai_test_platform` 目录，`env` 中填上述两个变量；`command` 为 `python`，`args` 为 `["-m", "mcp"]`。

详见 [MCP_SETUP.md](MCP_SETUP.md)。

---

## 五、常用运维命令

```bash
cd /opt/ai_test_platform

# 查看日志
docker compose logs -f app

# 重启
docker compose restart

# 停止
docker compose down

# 再次启动（数据在 volume 中保留）
docker compose up -d
```

数据在 Docker volume `app_data` 中，`docker compose down` 不会删数据；只有 `docker compose down -v` 才会删除 volume。

---

## 六、小结

| 步骤 | 说明 |
|------|------|
| 1 | 购买云服务器（1 核 2G 起），系统 Ubuntu 22.04，放通 22/80/443 |
| 2 | 安装 Docker 与 Docker Compose |
| 3 | 克隆或上传代码到 /opt/ai_test_platform，配置 .env（SECRET_KEY、DEBUG、CORS_ORIGINS） |
| 4 | 执行 `docker compose up -d --build` 启动后端 |
| 5 | 可选：Nginx 反代 + certbot 配置 HTTPS |
| 6 | 用户本机配置 MCP（BASE_URL 指向该服务器，token 为登录后获取） |
