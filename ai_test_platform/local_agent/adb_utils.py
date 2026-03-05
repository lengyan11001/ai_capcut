from __future__ import annotations

import subprocess
from typing import Any


def _run_adb(args: list[str], timeout: float = 10.0) -> str:
    cp = subprocess.run(["adb"] + args, capture_output=True, text=True, timeout=timeout)
    out = (cp.stdout or "") + ("\n" + cp.stderr if cp.stderr else "")
    return out.strip()


def list_adb_devices() -> list[dict[str, Any]]:
    output = _run_adb(["devices"])
    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("list of devices"):
            continue
        parts = line.split()
        if not parts:
            continue
        serial = parts[0]
        state = parts[1] if len(parts) > 1 else "unknown"
        rows.append(
            {
                "serial": serial,
                "adb_status": state,
                "appium_status": "unknown",
                "platform": "android",
            }
        )
    return rows


def ensure_adb_connect(serial: str) -> None:
    # 对 TCP/IP 设备，重复 connect 是幂等的
    if ":" in serial:
        _run_adb(["connect", serial], timeout=8.0)


def launch_reddit_via_adb(serial: str) -> None:
    # monkey 启动 Reddit 主界面，避免 Activity 变更导致命令失效
    _run_adb(["-s", serial, "shell", "monkey", "-p", "com.reddit.frontpage", "-c", "android.intent.category.LAUNCHER", "1"], timeout=15.0)

