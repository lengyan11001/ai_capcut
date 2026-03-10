from __future__ import annotations

import os


class AgentSettings:
    # 云端控制面地址，默认指向本机，实际环境通过 CLOUD_BASE_URL 覆盖
    cloud_base_url: str = os.environ.get("CLOUD_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    # agent 标识：所有环境代码一致，通过环境变量配置不同执行节点名称/Key
    agent_name: str = os.environ.get("AGENT_NAME", "pc-agent-1")
    agent_key: str = os.environ.get("AGENT_KEY", "pc-agent-1")
    agent_secret: str = os.environ.get("AGENT_SECRET", "")
    poll_interval_seconds: float = float(os.environ.get("POLL_INTERVAL_SECONDS", "3"))
    heartbeat_interval_seconds: float = float(os.environ.get("HEARTBEAT_INTERVAL_SECONDS", "10"))
    appium_server_url: str = os.environ.get("APPIUM_SERVER_URL", "http://127.0.0.1:4723")
    # Android: 留空表示自动发现当前 adb 在线设备；填值时用于精确绑定设备
    device_serials: list[str] = [
        x.strip() for x in os.environ.get("DEVICE_SERIALS", "").split(",") if x.strip()
    ]
    # iOS: 显式配置需要接入群控的设备 UDID，逗号分隔
    ios_device_serials: list[str] = [
        x.strip() for x in os.environ.get("IOS_DEVICE_SERIALS", "").split(",") if x.strip()
    ]
    # Appium Android 相关超时（毫秒），用于控制 UiAutomator2 安装和 adb 执行超时
    appium_uia2_install_timeout_ms: int = int(
        os.environ.get("APPIUM_UIA2_INSTALL_TIMEOUT_MS", "600000")
    )
    appium_adb_exec_timeout_ms: int = int(
        os.environ.get("APPIUM_ADB_EXEC_TIMEOUT_MS", "600000")
    )


settings = AgentSettings()

