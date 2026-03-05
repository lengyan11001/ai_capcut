from __future__ import annotations

import os
from typing import Any

import httpx

from .config import settings


class CloudClient:
    def __init__(self) -> None:
        direct = os.environ.get("CLOUD_BASE_URL_DIRECT", "").rstrip("/")
        self.base = direct or settings.cloud_base_url
        self.headers = {"Content-Type": "application/json"}
        if settings.agent_secret:
            self.headers["X-Agent-Secret"] = settings.agent_secret

    @staticmethod
    def _truncate(value: str, limit: int = 400) -> str:
        txt = value or ""
        if len(txt) <= limit:
            return txt
        return txt[:limit] + "...(truncated)"

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base}{path}"
        try:
            with httpx.Client(timeout=30.0) as client:
                r = client.post(url, json=payload, headers=self.headers)
        except httpx.TimeoutException as e:
            raise RuntimeError(f"{path} timeout on {url}: {e!s}") from e
        except httpx.RequestError as e:
            raise RuntimeError(f"{path} request error on {url}: {e!s}") from e
        try:
            data = r.json()
        except Exception:
            data = {"detail": (r.text or "")}
        if r.status_code >= 400:
            detail = ""
            if isinstance(data, dict):
                detail = str(data.get("detail") or "")
            if not detail:
                detail = self._truncate(r.text or "")
            server = r.headers.get("server") or "-"
            via = r.headers.get("via") or "-"
            raise RuntimeError(
                f"{path} failed: {r.status_code} detail={detail!r} "
                f"url={url} server={server} via={via}"
            )
        return data

    def register(self, host: str, devices: list[dict[str, Any]]) -> dict[str, Any]:
        return self._post(
            "/group-control/agents/register",
            {
                "name": settings.agent_name,
                "agent_key": settings.agent_key,
                "host": host,
                "devices": devices,
            },
        )

    def heartbeat(self, host: str, devices: list[dict[str, Any]]) -> dict[str, Any]:
        return self._post(
            f"/group-control/agents/{settings.agent_key}/heartbeat",
            {"host": host, "devices": devices},
        )

    def poll_next_task(self, serials: list[str]) -> dict[str, Any]:
        return self._post(
            f"/group-control/agents/{settings.agent_key}/next-task",
            {"device_serials": serials},
        )

    def report_task(self, task_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post(f"/group-control/tasks/{task_id}/report", payload)

