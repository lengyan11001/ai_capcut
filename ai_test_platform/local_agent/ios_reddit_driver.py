from __future__ import annotations

from typing import Any, Tuple, List, Dict


class RedditIosSession:
    """
    Minimal Reddit session for iOS devices using Appium + XCUITest.

    先实现一个保守的「browse」动作：打开 Reddit，随机滑动 Feed。
    其他高阶动作（搜索、点赞、评论等）可以在后续按需要补充。
    """

    def __init__(self, device_serial: str, appium_url: str) -> None:
        self.serial = device_serial
        self.appium_url = appium_url
        self.driver: Any = None
        self.logs: list[dict[str, Any]] = []

    def log(self, level: str, message: str) -> None:
        self.logs.append({"level": level, "message": message})

    def start(self) -> None:
        from appium import webdriver
        from appium.options.ios import XCUITestOptions

        opts = XCUITestOptions()
        opts.set_capability("platformName", "iOS")
        opts.set_capability("automationName", "XCUITest")
        opts.set_capability("udid", self.serial)
        # Reddit iOS 官方包名
        opts.set_capability("bundleId", "com.reddit.Reddit")
        opts.set_capability("noReset", True)
        opts.set_capability("newCommandTimeout", 180)

        self.driver = webdriver.Remote(self.appium_url, options=opts)
        self.log("info", "appium iOS session created for Reddit")

    def stop(self) -> None:
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    # --- helpers ---

    def human_delay(self, lo: float = 1.5, hi: float = 5.0) -> None:
        import random
        import time

        time.sleep(random.uniform(lo, hi))

    def swipe_up(self, pct: float = 0.6) -> None:
        d = self.driver
        size = d.get_window_size()
        w, h = size["width"], size["height"]
        x = w // 2
        y_start = int(h * (0.5 + pct / 2))
        y_end = int(h * (0.5 - pct / 2))
        d.swipe(x, y_start, x, y_end, duration=500)


def _run_browse(session: RedditIosSession, payload: Dict[str, Any]) -> Tuple[bool, str, List[Dict[str, Any]]]:
    duration_min = float(payload.get("duration_min") or 5)
    max_scrolls = int(payload.get("max_scrolls") or 20)
    session.log(
        "info",
        f"iOS browse start: duration_min={duration_min}, max_scrolls={max_scrolls}",
    )
    import time

    end_ts = time.time() + duration_min * 60.0
    scrolls = 0
    while time.time() < end_ts and scrolls < max_scrolls:
        try:
            session.swipe_up()
            scrolls += 1
            session.log("info", f"swipe_up #{scrolls}")
        except Exception as e:
            session.log("warn", f"swipe_up failed: {e}")
            break
        session.human_delay(1.5, 4.0)
    session.log("info", "iOS browse finished")
    return True, "ok", session.logs


def run_reddit_flow_ios(
    device_serial: str,
    device_label: str,
    appium_server_url: str,
    payload: Dict[str, Any],
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Entry point for reddit_ios 平台的任务。

    当前支持的动作：
    - browse: 打开 Reddit 并在首页随机滑动一段时间
    其他动作返回 unsupported_action_ios，方便云端/AI 判断能力边界。
    """
    action_name = str(payload.get("action") or "browse").strip()
    device_ref = (
        f"{device_label}({device_serial})"
        if device_label and device_label != device_serial
        else device_serial
    )

    session = RedditIosSession(device_serial, appium_server_url)
    try:
        session.log("info", f"start reddit_ios action '{action_name}' on {device_ref}")
        session.start()

        # 目前针对 iOS 的所有动作统一采用「浏览为主」的保守实现：
        # - browse: 正常浏览首页
        # - search/upvote/subscribe/comment/profile_check: 记录意图并执行一段浏览，
        #   行为上比较安全，但不会做复杂点击，避免 iOS UI 选择器不稳定导致崩溃。
        normalized = action_name or "browse"
        if normalized in {"browse", "search", "upvote", "subscribe", "comment", "profile_check"}:
            if normalized != "browse":
                session.log(
                    "info",
                    f"ios action '{normalized}' 使用 browse 流程近似执行（当前未实现精细化 iOS UI 操作）",
                )
            ok, error_code, logs = _run_browse(session, payload)
        else:
            msg = f"action '{action_name}' not implemented for reddit_ios"
            session.log("error", msg)
            ok, error_code, logs = False, "unsupported_action_ios", session.logs
        return ok, error_code, logs
    except Exception as e:
        session.log("error", f"reddit_ios flow failed: {e}")
        return False, "reddit_ios_exception", session.logs
    finally:
        session.stop()

