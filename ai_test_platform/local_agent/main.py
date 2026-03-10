from __future__ import annotations

import socket
import time
import traceback

from .adb_utils import ensure_adb_connect, list_adb_devices
from .ios_utils import build_ios_devices_from_serials
from .api_client import CloudClient
from .config import settings
from .reddit_driver import run_reddit_flow
from .ios_reddit_driver import run_reddit_flow_ios


def _host_name() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown-host"


def _collect_devices() -> list[dict]:
    android_out: list[dict] = []
    # Android 设备：通过 adb 发现。
    # 兼容两种模式：
    # 1) 传统模式：DEVICE_SERIALS 留空时自动发现所有在线设备；
    # 2) 纯 iOS 模式：仅配置 IOS_DEVICE_SERIALS 时跳过 adb，避免在未安装 adb 的环境报错。
    if settings.device_serials or not settings.ios_device_serials:
        for serial in settings.device_serials:
            ensure_adb_connect(serial)
        adb_rows = list_adb_devices()
        wanted = set(settings.device_serials)
        # 未指定 DEVICE_SERIALS 时，自动使用所有 adb 在线设备
        online_rows = [x for x in adb_rows if x.get("adb_status") == "device"]
        android_out = [x for x in online_rows if x.get("serial") in wanted] if wanted else online_rows

    # iOS 设备：基于 IOS_DEVICE_SERIALS 配置构造（UDID 列表）
    ios_out = build_ios_devices_from_serials(settings.ios_device_serials)

    return android_out + ios_out


def _run_loop() -> None:
    client = CloudClient()
    host = _host_name()
    last_hb = 0.0

    devices = _collect_devices()
    client.register(host=host, devices=devices)

    while True:
        now = time.time()
        try:
            devices = _collect_devices()
            if now - last_hb >= settings.heartbeat_interval_seconds:
                client.heartbeat(host=host, devices=devices)
                last_hb = now

            serials = [x.get("serial", "") for x in devices if x.get("serial")]
            polled = client.poll_next_task(serials=serials)
            task = (polled or {}).get("task")
            if not task:
                time.sleep(settings.poll_interval_seconds)
                continue

            task_id = int(task["id"])
            execution_id = int(task["execution_id"])
            device_serial = str(task.get("assigned_device_serial") or (serials[0] if serials else ""))
            device_label = str(task.get("assigned_device_label") or device_serial)
            payload = task.get("payload") or {}

            client.report_task(
                task_id,
                {
                    "execution_id": execution_id,
                    "status": "running",
                    "step": "start",
                    "logs": [{"level": "info", "message": f"task accepted on {device_serial}"}],
                },
            )

            platform = str(task.get("platform") or "reddit").strip()
            if platform == "reddit":
                ok, error_code, logs = run_reddit_flow(
                    device_serial=device_serial,
                    device_label=device_label,
                    appium_server_url=settings.appium_server_url,
                    payload=payload,
                )
            elif platform == "reddit_ios":
                ok, error_code, logs = run_reddit_flow_ios(
                    device_serial=device_serial,
                    device_label=device_label,
                    appium_server_url=settings.appium_server_url,
                    payload=payload,
                )
            else:
                ok, error_code, logs = False, "unsupported_platform", [
                    {
                        "level": "error",
                        "message": f"platform not supported: {platform} on {device_label}({device_serial})",
                    }
                ]

            client.report_task(
                task_id,
                {
                    "execution_id": execution_id,
                    "status": "success" if ok else "failed",
                    "step": "finish",
                    "error_code": None if ok else error_code,
                    "error_message": None if ok else f"task failed: {error_code}",
                    "logs": logs,
                },
            )
        except Exception as e:
            print(f"[agent] loop error: {e}")
            print(traceback.format_exc())
            time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    _run_loop()

