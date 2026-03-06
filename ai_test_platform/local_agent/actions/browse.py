"""browse action -- scroll through the Reddit home feed, randomly
pause on posts to simulate organic reading behaviour."""

from __future__ import annotations

import random
import time
from typing import Any

from .base import RedditSession


def execute(
    session: RedditSession,
    payload: dict[str, Any],
) -> tuple[bool, str, list[dict[str, Any]]]:
    duration_min = int(payload.get("duration_min", 8))
    max_scrolls = int(payload.get("max_scrolls", 30))
    deadline = time.time() + duration_min * 60
    scrolls = 0

    session.log("info", f"browse: duration_min={duration_min}, max_scrolls={max_scrolls}")

    # Ensure we're on the home tab
    home_btn = session.find_optional("desc", "Home")
    if home_btn:
        session.tap_element(home_btn)
        session.human_delay(1.0, 2.5)

    while scrolls < max_scrolls and time.time() < deadline:
        session.swipe_up()
        scrolls += 1

        # Randomly pause longer on some posts (simulates reading)
        if random.random() < 0.3:
            session.human_delay(3.0, 8.0)
        else:
            session.human_delay(1.0, 3.0)

        # Occasionally tap into a post and read, then go back
        if random.random() < 0.15:
            posts = session.find_all("id", "com.reddit.frontpage:id/post_title")
            if posts:
                target = random.choice(posts)
                if session.tap_element(target):
                    session.log("info", f"browse: opened post at scroll #{scrolls}")
                    session.human_delay(4.0, 12.0)
                    session.press_back()
                    session.human_delay(1.0, 2.0)

    session.log("info", f"browse: completed {scrolls} scrolls")
    return True, "", session.logs
