"""comment action -- open a post and leave a short template comment."""

from __future__ import annotations

import random
import time
from typing import Any

from .base import RedditSession

DEFAULT_TEMPLATES = [
    "Nice!",
    "Thanks for sharing",
    "Interesting",
    "Great post!",
    "This is cool",
    "Good read",
    "Helpful, thanks!",
    "I agree",
    "Well said",
]


def execute(
    session: RedditSession,
    payload: dict[str, Any],
) -> tuple[bool, str, list[dict[str, Any]]]:
    max_actions = int(payload.get("max_actions", 2))
    templates = payload.get("comment_templates") or DEFAULT_TEMPLATES

    session.log("info", f"comment: max_actions={max_actions}, templates_count={len(templates)}")

    comments_done = 0

    # Ensure home tab
    home_btn = session.find_optional("desc", "Home")
    if home_btn:
        session.tap_element(home_btn)
        session.human_delay(1.0, 2.0)

    for attempt in range(max_actions * 3):
        if comments_done >= max_actions:
            break

        session.swipe_up()
        session.human_delay(1.5, 3.5)

        # Try to open a post
        posts = session.find_all("id", "com.reddit.frontpage:id/post_title")
        if not posts:
            continue
        target = random.choice(posts)
        if not session.tap_element(target):
            continue
        session.human_delay(2.0, 4.0)

        # Find comment input / add comment button
        comment_btn = session.find_optional(
            "desc", "Add a comment"
        ) or session.find_optional(
            "id", "com.reddit.frontpage:id/action_comment"
        )
        if not comment_btn:
            session.press_back()
            session.human_delay(1.0, 2.0)
            continue

        session.tap_element(comment_btn)
        session.human_delay(1.5, 3.0)

        # Type the comment
        comment_input = session.find_optional("class", "android.widget.EditText", timeout=5.0)
        if not comment_input:
            session.press_back()
            session.human_delay(1.0, 2.0)
            continue

        text = random.choice(templates)
        for ch in text:
            comment_input.send_keys(ch)
            time.sleep(random.uniform(0.03, 0.12))
        session.human_delay(0.8, 1.5)

        # Submit
        submit_btn = session.find_optional("desc", "Post") or session.find_optional(
            "xpath", "//*[contains(@text, 'Post')]"
        )
        if submit_btn:
            session.tap_element(submit_btn)
            comments_done += 1
            session.log("info", f"comment: posted '{text}' (total={comments_done})")
            session.human_delay(2.0, 4.0)

        session.press_back()
        session.press_back()
        session.human_delay(1.0, 2.0)

    session.log("info", f"comment: done {comments_done} comments")
    return True, "", session.logs
