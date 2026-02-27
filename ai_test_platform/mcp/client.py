"""HTTP 客户端：调用测试平台后端 API，鉴权用 Bearer token。"""
import os
from typing import Any, Dict, Optional

import httpx

BASE_URL = os.environ.get("AI_TEST_PLATFORM_BASE_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("AI_TEST_PLATFORM_TOKEN", "")


def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h


def get(path: str) -> Dict[str, Any]:
    """GET 请求，返回 JSON。"""
    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{BASE_URL}{path}", headers=_headers())
        try:
            data = r.json()
        except Exception:
            data = {"detail": r.text or f"HTTP {r.status_code}"}
        if r.status_code >= 400:
            raise RuntimeError(data.get("detail", data) if isinstance(data, dict) else str(data))
        return data


def post(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """POST 请求，body 为 JSON，返回 JSON。"""
    with httpx.Client(timeout=60.0) as client:
        r = client.post(f"{BASE_URL}{path}", json=body, headers=_headers())
        try:
            data = r.json()
        except Exception:
            data = {"detail": r.text or f"HTTP {r.status_code}"}
        if r.status_code >= 400:
            raise RuntimeError(data.get("detail", data) if isinstance(data, dict) else str(data))
        return data
