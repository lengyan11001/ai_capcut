"""subscribe action -- navigate to a subreddit and tap Join."""

from __future__ import annotations

import random
from typing import Any

from .base import RedditSession


def execute(
    session: RedditSession,
    payload: dict[str, Any],
) -> tuple[bool, str, list[dict[str, Any]]]:
    subreddit = str(payload.get("subreddit_name", "")).strip()

    if subreddit:
        session.log("info", f"subscribe: navigating to r/{subreddit}")
        # Use search to find the subreddit
        search_btn = session.find_optional("desc", "Search") or session.find_optional(
            "id", "com.reddit.frontpage:id/search"
        )
        if search_btn:
            session.tap_element(search_btn)
            session.human_delay(1.0, 2.0)

        search_input = session.find_optional(
            "id", "com.reddit.frontpage:id/search_input"
        ) or session.find_optional("class", "android.widget.EditText")
        if search_input:
            search_input.clear()
            search_input.send_keys(f"r/{subreddit}")
            session.human_delay(0.8, 1.5)
            try:
                session.driver.press_keycode(66)
            except Exception:
                pass
            session.human_delay(2.0, 4.0)

            # Try to find and tap the community result
            community = session.find_optional(
                "xpath",
                f"//*[contains(@text, 'r/{subreddit}')]",
                timeout=5.0,
            )
            if community:
                session.tap_element(community)
                session.human_delay(2.0, 3.5)
    else:
        session.log("info", "subscribe: browsing recommendations for a community to join")
        # Tap Explore/Communities tab
        explore_btn = session.find_optional("desc", "Explore") or session.find_optional(
            "desc", "Communities"
        )
        if explore_btn:
            session.tap_element(explore_btn)
            session.human_delay(2.0, 4.0)
        # Scroll a bit
        for _ in range(random.randint(2, 5)):
            session.swipe_up()
            session.human_delay(1.0, 2.5)

    # Look for a Join button
    join_btn = session.find_optional("desc", "Join") or session.find_optional(
        "xpath", "//*[contains(@text, 'Join')]"
    )
    if join_btn:
        session.tap_element(join_btn)
        session.log("info", f"subscribe: tapped Join for {'r/' + subreddit if subreddit else 'recommended community'}")
        session.human_delay(1.5, 3.0)
    else:
        session.log("warn", "subscribe: Join button not found")

    session.press_back()
    session.press_back()
    return True, "", session.logs
