"""search action -- tap the search icon, type keyword, browse results."""

from __future__ import annotations

import random
import time
from typing import Any

from .base import RedditSession


def execute(
    session: RedditSession,
    payload: dict[str, Any],
) -> tuple[bool, str, list[dict[str, Any]]]:
    keyword = str(payload.get("keyword", "")).strip()
    if not keyword:
        session.log("warn", "search: no keyword provided, falling back to browse")
        from .browse import execute as browse_exec
        return browse_exec(session, payload)

    duration_min = int(payload.get("duration_min", 6))
    max_scrolls = int(payload.get("max_scrolls", 15))
    deadline = time.time() + duration_min * 60

    session.log("info", f"search: keyword='{keyword}', duration_min={duration_min}")

    # Tap search icon (bottom nav bar or top)
    search_btn = session.find_optional("desc", "Search") or session.find_optional(
        "id", "com.reddit.frontpage:id/search"
    )
    if not search_btn:
        session.log("warn", "search: cannot find search button")
        return False, "search_button_not_found", session.logs
    session.tap_element(search_btn)
    session.human_delay(1.0, 2.5)

    # Type into search field
    search_input = session.find_optional(
        "id", "com.reddit.frontpage:id/search_input"
    ) or session.find_optional("class", "android.widget.EditText")
    if not search_input:
        session.log("warn", "search: cannot find search input")
        return False, "search_input_not_found", session.logs

    search_input.clear()
    # Type character by character with small delays to mimic human typing
    for ch in keyword:
        search_input.send_keys(ch)
        time.sleep(random.uniform(0.05, 0.18))
    session.human_delay(0.8, 1.5)

    # Submit search (press Enter)
    try:
        session.driver.press_keycode(66)  # KEYCODE_ENTER
    except Exception:
        pass
    session.human_delay(2.0, 4.0)

    scrolls = 0
    while scrolls < max_scrolls and time.time() < deadline:
        session.swipe_up()
        scrolls += 1
        if random.random() < 0.25:
            session.human_delay(3.0, 7.0)
        else:
            session.human_delay(1.0, 3.0)

        # Randomly open a search result
        if random.random() < 0.2:
            posts = session.find_all("id", "com.reddit.frontpage:id/post_title")
            if posts:
                target = random.choice(posts)
                if session.tap_element(target):
                    session.log("info", f"search: opened result at scroll #{scrolls}")
                    session.human_delay(4.0, 10.0)
                    session.press_back()
                    session.human_delay(1.0, 2.0)

    session.log("info", f"search: completed {scrolls} scrolls for '{keyword}'")
    session.press_back()
    return True, "", session.logs
