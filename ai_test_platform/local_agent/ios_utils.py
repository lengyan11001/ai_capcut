from __future__ import annotations

from typing import Any, List, Dict


def build_ios_devices_from_serials(serials: List[str]) -> List[Dict[str, Any]]:
    """
    Build minimal iOS device descriptors for the agent to register with the cloud.

    We rely on IOS_DEVICE_SERIALS (UDID 列表) 作为唯一标识，不在这里做真实设备探测，
    以保持实现简单、跨平台可用。只要 UDID 正确且 Appium/WDA 配置正常，就可以建立会话。
    """
    rows: list[dict[str, Any]] = []
    for raw in serials:
        serial = (raw or "").strip()
        if not serial:
            continue
        label_suffix = serial[-6:] if len(serial) > 6 else serial
        meta: dict[str, Any] = {
            "device_uid": serial,
            "platform": "ios",
            "brand": "Apple",
            "model": "iPhone",
            "device_label": f"iOS-{label_suffix}",
        }
        rows.append(
            {
                "serial": serial,
                "adb_status": "n/a",
                "appium_status": "unknown",
                "platform": "ios",
                "meta": meta,
            }
        )
    return rows

