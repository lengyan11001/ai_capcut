from __future__ import annotations

import os


class AgentSettings:
    cloud_base_url: str = os.environ.get("CLOUD_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    agent_name: str = os.environ.get("AGENT_NAME", "pc-agent-1")
    agent_key: str = os.environ.get("AGENT_KEY", "pc-agent-1")
    agent_secret: str = os.environ.get("AGENT_SECRET", "")
    poll_interval_seconds: float = float(os.environ.get("POLL_INTERVAL_SECONDS", "3"))
    heartbeat_interval_seconds: float = float(os.environ.get("HEARTBEAT_INTERVAL_SECONDS", "10"))
    appium_server_url: str = os.environ.get("APPIUM_SERVER_URL", "http://127.0.0.1:4723")
    device_serials: list[str] = [
        x.strip() for x in os.environ.get("DEVICE_SERIALS", "192.168.1.93:5555").split(",") if x.strip()
    ]


settings = AgentSettings()

