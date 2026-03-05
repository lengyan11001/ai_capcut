# Local Agent（本地执行节点）

用于连接本地 ADB 手机并主动从云端 `ai_test_platform` 拉取群控任务执行。

## 1) 安装依赖

```bash
cd ai_test_platform
python -m venv .venv-agent
source .venv-agent/bin/activate   # Windows: .venv-agent\\Scripts\\activate
pip install -r requirements-agent.txt
```

## 2) 环境变量

```bash
export CLOUD_BASE_URL=http://<腾讯云IP>:8000
# 推荐：Agent 轮询/心跳直连后端（内网或回环），避免高频请求走公网 Nginx 导致 502
# export CLOUD_BASE_URL_DIRECT=http://127.0.0.1:8000
export AGENT_NAME=pc-agent-1
export AGENT_KEY=pc-agent-1
export AGENT_SECRET=<与后端CONTROL_AGENT_SECRET一致>
export APPIUM_SERVER_URL=http://127.0.0.1:4723
# 可选：不填表示自动发现当前 adb 在线设备；填值可精确绑定
# export DEVICE_SERIALS=R58Mxxxxxxx,192.168.1.93:5555
```

## 3) 启动 Agent

```bash
python -m local_agent.main
```

## 3.2) `/next-task` 502 诊断（代理 vs 直连）

当出现 `next-task failed: 502` 时，可用下列命令一次对比两条链路：

```bash
python -m local_agent.diagnose_next_task \
  --proxy-base http://<公网域名或IP>:8000 \
  --direct-base http://127.0.0.1:8000 \
  --agent-key pc-agent-1 \
  --agent-secret <AGENT_SECRET> \
  --serials 192.168.1.93:5555
```

输出会同时给出 `status_code/server/via/body`，便于确认 502 是否由代理层引入。

## 3.3) 启动前绑定校验（推荐）

先维护 `docs/ASSET_BINDING_TEMPLATE.csv`（可重命名为你自己的文件），再执行：

```bash
python -m local_agent.check_asset_bindings docs/ASSET_BINDING_TEMPLATE.csv
```

校验规则：
- 同一个 `reddit_username` 不应绑定多个 `device_serial`
- 同一个 `reddit_username` 不应绑定多个 `proxy_exit_ip`
- 一个设备绑定多个账号仅给出告警（建议减少切号）

## 3.4) 稳定性回归（轮询压测）

用于验证 `next-task` 在 10-15 分钟内是否存在 502/超时：

```bash
python -m local_agent.check_next_task_stability \
  --base-url http://127.0.0.1:8000 \
  --agent-key pc-agent-1 \
  --agent-secret <AGENT_SECRET> \
  --serials 192.168.1.93:5555 \
  --loops 600 \
  --interval 1
```

若输出里 `errors` 为空且 `ok` 接近 `loops`，说明轮询链路稳定。

## 4) 说明

- Agent 只出站访问云端，不暴露本地 ADB 到公网。
- 目前已接入 Reddit POC 流程（启动应用 + 建立 Appium 会话 + 基础动作参数化）。
- 后续可按平台新增驱动（如 `tiktok_driver.py`）并在主循环中分发。
- Agent 会在设备上报中附带 `meta.device_uid`（优先硬件序列号），用于账号-设备稳定绑定。

