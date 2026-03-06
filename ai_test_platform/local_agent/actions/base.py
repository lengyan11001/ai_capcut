"""RedditSession -- manages Appium driver lifecycle and provides
common UI helpers (wait, swipe, random delay, element location)
shared across all action modules."""

from __future__ import annotations

import random
import time
from typing import Any

from ..adb_utils import launch_reddit_via_adb
from ..config import settings

REDDIT_PACKAGE = "com.reddit.frontpage"


class RedditSession:
    """Wraps an Appium UiAutomator2 session against the Reddit app."""

    def __init__(self, device_serial: str, appium_url: str | None = None):
        self.serial = device_serial
        self.appium_url = appium_url or settings.appium_server_url
        self.driver: Any = None
        self.logs: list[dict[str, Any]] = []

    def log(self, level: str, message: str) -> None:
        self.logs.append({"level": level, "message": message})

    # -- lifecycle --

    def start(self) -> None:
        launch_reddit_via_adb(self.serial)
        self.log("info", "reddit launched via adb")

        from appium import webdriver
        from appium.options.android import UiAutomator2Options

        opts = UiAutomator2Options()
        opts.set_capability("platformName", "Android")
        opts.set_capability("automationName", "UiAutomator2")
        opts.set_capability("udid", self.serial)
        opts.set_capability("appPackage", REDDIT_PACKAGE)
        opts.set_capability("noReset", True)
        opts.set_capability("newCommandTimeout", 180)
        opts.set_capability("uiautomator2ServerInstallTimeout", settings.appium_uia2_install_timeout_ms)
        opts.set_capability("adbExecTimeout", settings.appium_adb_exec_timeout_ms)

        self.driver = webdriver.Remote(self.appium_url, options=opts)
        self.log("info", "appium session created")

    def stop(self) -> None:
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def __enter__(self) -> "RedditSession":
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop()

    # -- common helpers --

    def human_delay(self, lo: float = 1.5, hi: float = 5.0) -> None:
        """Sleep a random interval to simulate human pacing."""
        time.sleep(random.uniform(lo, hi))

    def swipe_up(self, pct: float = 0.55) -> None:
        """Swipe upward on the screen (scroll down through feed)."""
        d = self.driver
        size = d.get_window_size()
        w, h = size["width"], size["height"]
        x = w // 2
        y_start = int(h * (0.5 + pct / 2))
        y_end = int(h * (0.5 - pct / 2))
        d.swipe(x, y_start, x, y_end, duration=random.randint(350, 700))

    def swipe_down(self, pct: float = 0.4) -> None:
        """Swipe downward on the screen (scroll up)."""
        d = self.driver
        size = d.get_window_size()
        w, h = size["width"], size["height"]
        x = w // 2
        y_start = int(h * (0.5 - pct / 2))
        y_end = int(h * (0.5 + pct / 2))
        d.swipe(x, y_start, x, y_end, duration=random.randint(300, 600))

    def find_optional(self, by: str, value: str, timeout: float = 5.0) -> Any:
        """Try to find an element; return None instead of raising."""
        from appium.webdriver.common.appiumby import AppiumBy
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        by_map = {
            "id": AppiumBy.ID,
            "xpath": AppiumBy.XPATH,
            "desc": AppiumBy.ACCESSIBILITY_ID,
            "class": AppiumBy.CLASS_NAME,
            "uia": AppiumBy.ANDROID_UIAUTOMATOR,
        }
        sel = by_map.get(by, by)
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((sel, value))
            )
        except Exception:
            return None

    def find_all(self, by: str, value: str) -> list:
        from appium.webdriver.common.appiumby import AppiumBy

        by_map = {
            "id": AppiumBy.ID,
            "xpath": AppiumBy.XPATH,
            "desc": AppiumBy.ACCESSIBILITY_ID,
            "class": AppiumBy.CLASS_NAME,
            "uia": AppiumBy.ANDROID_UIAUTOMATOR,
        }
        sel = by_map.get(by, by)
        try:
            return self.driver.find_elements(sel, value)
        except Exception:
            return []

    def tap_element(self, el: Any) -> bool:
        try:
            el.click()
            return True
        except Exception:
            return False

    def current_package(self) -> str:
        try:
            return self.driver.current_package or ""
        except Exception:
            return ""

    def press_back(self) -> None:
        try:
            self.driver.press_keycode(4)
        except Exception:
            pass
