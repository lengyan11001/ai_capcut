"""upvote action -- browse the feed and probabilistically upvote posts."""

from __future__ import annotations

import random
import time
from typing import Any

from .base import RedditSession


def execute(
    session: RedditSession,
    payload: dict[str, Any],
) -> tuple[bool, str, list[dict[str, Any]]]:
    duration_min = int(payload.get("duration_min", 10))
    max_actions = int(payload.get("max_actions", 20))
    upvote_ratio = float(payload.get("upvote_ratio", 0.05))
    deadline = time.time() + duration_min * 60

    session.log("info", f"upvote: duration_min={duration_min}, max_actions={max_actions}, ratio={upvote_ratio}")

    upvotes_done = 0
    scrolls = 0

    # Ensure home tab
    home_btn = session.find_optional("desc", "Home")
    if home_btn:
        session.tap_element(home_btn)
        session.human_delay(1.0, 2.0)

    while upvotes_done < max_actions and time.time() < deadline:
        session.swipe_up()
        scrolls += 1
        session.human_delay(1.0, 3.0)

        if random.random() < upvote_ratio:
            upvote_btns = session.find_all("desc", "Upvote")
            if not upvote_btns:
                upvote_btns = session.find_all("id", "com.reddit.frontpage:id/upvote")
            if upvote_btns:
                btn = random.choice(upvote_btns)
                if session.tap_element(btn):
                    upvotes_done += 1
                    session.log("info", f"upvote: +1 (total={upvotes_done}) at scroll #{scrolls}")
                    session.human_delay(1.5, 4.0)

    session.log("info", f"upvote: done {upvotes_done} upvotes in {scrolls} scrolls")
    return True, "", session.logs
