"""HTTP 客户端：调用测试平台后端 API，鉴权用 Bearer token。"""
import os
from typing import Any, Dict, Optional

import httpx

from .context import get_platform_token

BASE_URL = os.environ.get("AI_TEST_PLATFORM_BASE_URL", "http://localhost:8000").rstrip("/")


def _get_token() -> str:
    """优先用请求上下文 token（HTTP 模式），否则用环境变量。"""
    t = get_platform_token()
    if t:
        return t
    return os.environ.get("AI_TEST_PLATFORM_TOKEN", "")


def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    token = _get_token()
    if token:
        h["Authorization"] = f"Bearer {token}"
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
