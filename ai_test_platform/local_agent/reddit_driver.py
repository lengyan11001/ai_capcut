from __future__ import annotations

from typing import Any

from .adb_utils import launch_reddit_via_adb


def run_reddit_flow(
    device_serial: str,
    appium_server_url: str,
    payload: dict[str, Any],
) -> tuple[bool, str, list[dict[str, Any]]]:
    """
    Reddit POC 流程（一期）：
    - 通过 ADB 拉起 Reddit
    - 尝试用 Appium 建立会话并做最基础探测
    """
    logs: list[dict[str, Any]] = []
    logs.append({"level": "info", "message": f"start reddit flow on {device_serial}"})
    launch_reddit_via_adb(device_serial)
    logs.append({"level": "info", "message": "reddit app launch requested via adb"})

    try:
        from appium import webdriver
        from appium.options.android import UiAutomator2Options
    except Exception as e:
        logs.append({"level": "error", "message": f"appium client import failed: {e}"})
        return False, "appium_import_error", logs

    options = UiAutomator2Options()
    options.set_capability("platformName", "Android")
    options.set_capability("automationName", "UiAutomator2")
    options.set_capability("udid", device_serial)
    options.set_capability("appPackage", "com.reddit.frontpage")
    options.set_capability("noReset", True)
    options.set_capability("newCommandTimeout", 120)

    driver = None
    try:
        driver = webdriver.Remote(appium_server_url, options=options)
        logs.append({"level": "info", "message": "appium session created"})
        current_package = ""
        try:
            current_package = driver.current_package or ""
        except Exception:
            pass
        logs.append({"level": "info", "message": f"current_package={current_package}"})

        # 参数化动作（仅预留，一期先跑通）
        keyword = str(payload.get("keyword") or "").strip()
        action = str(payload.get("action") or "browse").strip()
        if keyword:
            logs.append({"level": "info", "message": f"keyword={keyword}"})
        logs.append({"level": "info", "message": f"action={action}"})
        return True, "", logs
    except Exception as e:
        logs.append({"level": "error", "message": f"reddit flow failed: {e}"})
        return False, "reddit_flow_failed", logs
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

