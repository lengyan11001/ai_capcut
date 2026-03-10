## 本地 Agent 启动示例（Android / iOS 通用）

> 说明：本文件只包含示例命令，所有实际的 IP、密钥、UDID 请在你自己的终端里通过环境变量配置，不要直接写死到代码里，这样多人协作时不会互相覆盖配置。

### 一、通用前置步骤（所有机器都一样）

在项目根目录创建并激活虚拟环境（你已经做过一次，这里作为备用记录）：

```bash
cd /Users/sadfas/Documents/local/ai_capcut/ai_test_platform
python3 -m venv .venv-agent
source .venv-agent/bin/activate
pip install -r requirements-agent.txt
```

启动 Appium（全平台通用）：

```bash
cd /Users/sadfas/Documents/local/ai_capcut
npx appium --address 127.0.0.1 --port 4723
```

### 二、环境变量配置示例（推荐每台机器自己在终端里 export）

#### 1. 通用环境变量（云端地址、Agent 身份）

```bash
cd /Users/sadfas/Documents/local/ai_capcut/ai_test_platform
source .venv-agent/bin/activate

# 云端控制面地址：改成你的后端实际地址
export CLOUD_BASE_URL=http://159.75.168.18:8000

# 当前这台机器上的 Agent 标识（每台机器配不同的名字/Key）
export AGENT_NAME=pc-agent-ios-1
export AGENT_KEY=pc-agent-ios-1

# 和后端 .env 里的 CONTROL_AGENT_SECRET 保持一致
export AGENT_SECRET=b2ac5221fbf0315ac3e563c6916319cab2db8076c2f548ab70789e07ce458d5e

# Appium 地址（通常不用改）
export APPIUM_SERVER_URL=http://127.0.0.1:4723
```
export IOS_DEVICE_SERIALS=00008110-0019718C1ABA201E

#### 2. Android 设备示例（可选）

```bash
# Android 设备 adb 序列号，多个用逗号
export DEVICE_SERIALS=192.168.1.93:5555,192.168.1.94:5555
```

#### 3. iOS 设备示例（重点）

```bash
# iOS 设备 UDID，多个用逗号
export IOS_DEVICE_SERIALS=00008110-0019718C1ABA201E
```

> 说明：同一份代码在不同电脑上使用时，只需要每台机器自己在终端里设置以上环境变量即可，`local_agent/config.py` 不需要修改，这样 git 拉取/推送不会互相覆盖配置。

### 三、启动本地 Agent

在完成以上环境变量配置后，在同一个终端中启动：

```bash
cd /Users/sadfas/Documents/local/ai_capcut/ai_test_platform
source .venv-agent/bin/activate
python -m local_agent.main
```

- 如果同时配置了 `DEVICE_SERIALS` 和 `IOS_DEVICE_SERIALS`，这台 Agent 会同时上报 Android 和 iOS 设备；
- 如果只配置了 `IOS_DEVICE_SERIALS`，则仅作为 iOS 群控节点；
- 设备会出现在前端的「群控 → 设备列表」里，`platform` 字段区分为 `android` / `ios`。

