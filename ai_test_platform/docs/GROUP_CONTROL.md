# 群控系统部署与扩展（一期）

本文面向当前架构：
- 控制面：腾讯云 `ai_test_platform`
- 执行面：本地 PC（ADB 连接手机）运行 `local_agent`
- 自动化：Appium + UiAutomator2

## 1. 云端后端配置

在云端 `ai_test_platform/.env` 中增加：

```env
CONTROL_AGENT_SECRET=replace_with_strong_secret
CONTROL_TASK_LEASE_SECONDS=120
CONTROL_AGENT_OFFLINE_SECONDS=90
```

重启服务：

```bash
docker compose up -d --build app
```

## 2. 外网访问（IP 阶段）

### 2.1 Nginx 反向代理（先用 IP）

```nginx
server {
    listen 80;
    server_name _;

    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

> 无域名阶段先用 `http://<腾讯云IP>/`；有域名后切到 HTTPS 证书。

### 2.2 基础安全建议

- 仅开放必要端口（80/443），关闭公网对 8000 的直接暴露。
- `CONTROL_AGENT_SECRET` 必须设置并定期轮换。
- 不要对公网开放 ADB 5555 端口。

## 3. 本地执行机部署（你的 PC）

### 3.1 准备依赖

```bash
cd ai_test_platform
python -m venv .venv-agent
source .venv-agent/bin/activate   # Windows: .venv-agent\Scripts\activate
pip install -r requirements-agent.txt
```

### 3.2 配置环境变量

```bash
export CLOUD_BASE_URL=http://<腾讯云IP>
export AGENT_NAME=pc-agent-1
export AGENT_KEY=pc-agent-1
export AGENT_SECRET=<与CONTROL_AGENT_SECRET一致>
export APPIUM_SERVER_URL=http://127.0.0.1:4723
export DEVICE_SERIALS=192.168.1.93:5555
```

### 3.3 启动 Appium 与 Agent

```bash
adb connect 192.168.1.93:5555
appium --address 127.0.0.1 --port 4723
python -m local_agent.main
```

## 4. 任务打通步骤（Reddit）

1. 浏览器登录云端控制台，进入「群控」页。
2. 确认设备列表出现 `192.168.1.93:5555`。
3. 创建任务（平台 `reddit`，类型 `reddit_flow`）。
4. 等待 Agent 拉取执行，查看任务详情日志。

## 5. 多设备（20 台）扩展

- 单机并发建议从 2~4 台起步，逐步压测。
- 每台手机保持独立账号、独立代理网络（减少风控关联）。
- `DEVICE_SERIALS` 传多个：`serial1,serial2,...`
- 建议在 Agent 内增加「每设备并发锁」和「失败隔离名单」。

## 6. 多执行机扩展（后续）

- 每台执行机部署一个 `local_agent`，使用唯一 `AGENT_KEY`。
- 云端按设备归属自动派发任务；任务可指定 `target_device_id`。
- 建议新增节点标签（地区/运营商/机型），用于任务路由策略。

## 7. TikTok 扩展路径

- 新增驱动文件：`local_agent/tiktok_driver.py`
- 在 `local_agent/main.py` 按 `platform` 分发驱动
- 复用同一套任务模型、日志上报、审计面板

