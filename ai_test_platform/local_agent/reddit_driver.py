"""Reddit flow driver -- routes incoming task payloads to the
appropriate action module via the action catalog."""

from __future__ import annotations

from typing import Any

from .actions.base import RedditSession
from .actions.catalog import get_action_handler


def run_reddit_flow(
    device_serial: str,
    device_label: str,
    appium_server_url: str,
    payload: dict[str, Any],
) -> tuple[bool, str, list[dict[str, Any]]]:
    action_name = str(payload.get("action") or "browse").strip()
    device_ref = (
        f"{device_label}({device_serial})"
        if device_label and device_label != device_serial
        else device_serial
    )

    handler = get_action_handler(action_name)
    if handler is None:
        return False, "unknown_action", [
            {"level": "error", "message": f"unknown action '{action_name}' on {device_ref}"}
        ]

    session = RedditSession(device_serial, appium_server_url)
    try:
        session.log("info", f"start reddit action '{action_name}' on {device_ref}")
        session.start()
        ok, error_code, logs = handler(session, payload)
        # Merge session-level logs with action logs (action may return session.logs directly)
        if logs is not session.logs:
            session.logs.extend(logs)
        return ok, error_code, session.logs
    except Exception as e:
        session.log("error", f"action '{action_name}' failed: {e}")
        return False, "action_exception", session.logs
    finally:
        session.stop()
