"""profile_check action -- navigate to the user profile page,
read karma value and account username, include them in result logs
so the server can update binding state."""

from __future__ import annotations

import re
from typing import Any

from .base import RedditSession


def execute(
    session: RedditSession,
    payload: dict[str, Any],
) -> tuple[bool, str, list[dict[str, Any]]]:
    session.log("info", "profile_check: navigating to profile")

    # Tap the profile/avatar icon (usually bottom-right nav)
    profile_btn = session.find_optional("desc", "My profile") or session.find_optional(
        "desc", "Account"
    ) or session.find_optional(
        "id", "com.reddit.frontpage:id/bottom_nav_avatar"
    )
    if not profile_btn:
        # Fallback: try the navigation drawer
        profile_btn = session.find_optional("desc", "Navigation menu")
        if profile_btn:
            session.tap_element(profile_btn)
            session.human_delay(1.0, 2.0)
            profile_btn = session.find_optional("xpath", "//*[contains(@text, 'Profile')]")

    if not profile_btn:
        session.log("warn", "profile_check: cannot locate profile entry point")
        return False, "profile_not_found", session.logs

    session.tap_element(profile_btn)
    session.human_delay(2.0, 4.0)

    # Read username
    username = ""
    username_el = session.find_optional(
        "id", "com.reddit.frontpage:id/username"
    ) or session.find_optional(
        "xpath", "//*[starts-with(@text, 'u/')]"
    )
    if username_el:
        raw = username_el.text or ""
        username = raw.replace("u/", "").strip()

    # Read karma (look for text that contains a number near "karma")
    karma = 0
    karma_el = session.find_optional(
        "id", "com.reddit.frontpage:id/karma_count"
    ) or session.find_optional(
        "xpath", "//*[contains(@text, 'karma')]"
    )
    if karma_el:
        raw_text = karma_el.text or ""
        numbers = re.findall(r"[\d,]+", raw_text)
        if numbers:
            karma = int(numbers[0].replace(",", ""))

    # Also check if there are any visible warnings/restrictions
    restricted = False
    restriction_el = session.find_optional(
        "xpath", "//*[contains(@text, 'restricted') or contains(@text, 'suspended')]",
        timeout=2.0,
    )
    if restriction_el:
        restricted = True

    result = {
        "username": username,
        "karma": karma,
        "restricted": restricted,
    }
    session.log("info", f"profile_check: username={username}, karma={karma}, restricted={restricted}")
    # Tag the result as structured data for the server to parse
    session.log("data", f"account_state={result}")

    session.press_back()
    return True, "", session.logs
