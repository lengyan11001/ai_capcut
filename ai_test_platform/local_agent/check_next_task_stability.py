from __future__ import annotations

import argparse
import json
import time

import httpx


def main() -> None:
    ap = argparse.ArgumentParser(description="Probe next-task endpoint in a loop for stability check.")
    ap.add_argument("--base-url", required=True, help="API base URL, e.g. http://127.0.0.1:8000")
    ap.add_argument("--agent-key", required=True, help="agent key, e.g. pc-agent-1")
    ap.add_argument("--agent-secret", default="", help="X-Agent-Secret")
    ap.add_argument("--serials", default="", help="comma-separated serials")
    ap.add_argument("--loops", type=int, default=50, help="total loop count")
    ap.add_argument("--interval", type=float, default=1.0, help="seconds between loops")
    args = ap.parse_args()

    serials = [x.strip() for x in args.serials.split(",") if x.strip()]
    url = f"{args.base_url.rstrip('/')}/group-control/agents/{args.agent_key}/next-task"
    headers = {"Content-Type": "application/json"}
    if args.agent_secret:
        headers["X-Agent-Secret"] = args.agent_secret

    result = {"ok": 0, "errors": {}, "samples": []}
    with httpx.Client(timeout=20.0) as client:
        for idx in range(args.loops):
            code = None
            body = ""
            try:
                r = client.post(url, json={"device_serials": serials}, headers=headers)
                code = r.status_code
                body = (r.text or "")[:180]
            except Exception as e:  # noqa: BLE001
                code = "EXC"
                body = str(e)[:180]
            key = str(code)
            if key.startswith("2"):
                result["ok"] += 1
            else:
                result["errors"][key] = result["errors"].get(key, 0) + 1
                if len(result["samples"]) < 8:
                    result["samples"].append({"idx": idx, "status": key, "body": body})
            time.sleep(max(args.interval, 0.0))

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
