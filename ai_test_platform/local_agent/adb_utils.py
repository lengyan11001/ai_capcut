from __future__ import annotations

import os
import subprocess
from typing import Any


def _adb_executable() -> str:
    configured = (os.environ.get("ADB_PATH") or "").strip()
    if configured and os.path.exists(configured):
        return configured
    candidates = [
        os.path.expandvars(
            r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe"
        ),
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
        r"C:\platform-tools\adb.exe",
    ]
    for item in candidates:
        if os.path.exists(item):
            return item
    return "adb"


def _run_adb(args: list[str], timeout: float = 10.0) -> str:
    cp = subprocess.run([_adb_executable()] + args, capture_output=True, text=True, timeout=timeout)
    out = (cp.stdout or "") + ("\n" + cp.stderr if cp.stderr else "")
    return out.strip()


def _run_adb_for_device(serial: str, args: list[str], timeout: float = 5.0) -> str:
    return _run_adb(["-s", serial] + args, timeout=timeout)


def _safe_getprop(serial: str, prop: str) -> str:
    try:
        return _run_adb_for_device(serial, ["shell", "getprop", prop], timeout=4.0).strip()
    except Exception:
        return ""


def _safe_android_id(serial: str) -> str:
    try:
        out = _run_adb_for_device(serial, ["shell", "settings", "get", "secure", "android_id"], timeout=4.0)
        return out.strip()
    except Exception:
        return ""


def _build_device_meta(serial: str) -> dict[str, Any]:
    # 优先使用硬件序列号作为稳定标识，缺失时降级为 adb serial
    hw_serial = _safe_getprop(serial, "ro.serialno") or _safe_getprop(serial, "ro.boot.serialno")
    device_uid = hw_serial or serial
    return {
        "device_uid": device_uid,
        "hw_serial": hw_serial or None,
        "model": _safe_getprop(serial, "ro.product.model") or None,
        "brand": _safe_getprop(serial, "ro.product.brand") or None,
        "android_id": _safe_android_id(serial) or None,
    }


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
        meta = _build_device_meta(serial) if state == "device" else {"device_uid": serial}
        rows.append(
            {
                "serial": serial,
                "adb_status": state,
                "appium_status": "unknown",
                "platform": "android",
                "meta": meta,
            }
        )
    return rows


def ensure_adb_connect(serial: str) -> None:
    # 对 TCP/IP 设备，重复 connect 是幂等的
    if ":" in serial:
        try:
            _run_adb(["connect", serial], timeout=8.0)
        except Exception:
            # IP 变化或设备暂时离线时不抛异常，交由后续 adb devices 结果决定
            return


def launch_reddit_via_adb(serial: str) -> None:
    # monkey 启动 Reddit 主界面，避免 Activity 变更导致命令失效
    _run_adb(["-s", serial, "shell", "monkey", "-p", "com.reddit.frontpage", "-c", "android.intent.category.LAUNCHER", "1"], timeout=15.0)

