from __future__ import annotations

import argparse
import json
from typing import Any

import httpx


def _one_call(base_url: str, agent_key: str, agent_secret: str, serials: list[str]) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/group-control/agents/{agent_key}/next-task"
    headers = {"Content-Type": "application/json"}
    if agent_secret:
        headers["X-Agent-Secret"] = agent_secret
    payload = {"device_serials": serials}
    with httpx.Client(timeout=20.0) as client:
        r = client.post(url, json=payload, headers=headers)
    body_text = r.text or ""
    try:
        body = r.json()
    except Exception:
        body = {"raw": body_text[:600]}
    return {
        "url": url,
        "status_code": r.status_code,
        "server": r.headers.get("server", ""),
        "via": r.headers.get("via", ""),
        "body": body,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare /next-task via proxy and direct backend.")
    ap.add_argument("--proxy-base", required=True, help="e.g. https://your-nginx.example.com")
    ap.add_argument("--direct-base", required=True, help="e.g. http://127.0.0.1:8000")
    ap.add_argument("--agent-key", required=True, help="agent key, e.g. pc-agent-1")
    ap.add_argument("--agent-secret", default="", help="X-Agent-Secret")
    ap.add_argument("--serials", default="", help="comma-separated serials")
    args = ap.parse_args()

    serials = [x.strip() for x in args.serials.split(",") if x.strip()]
    out = {
        "proxy": _one_call(args.proxy_base, args.agent_key, args.agent_secret, serials),
        "direct": _one_call(args.direct_base, args.agent_key, args.agent_secret, serials),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
