from __future__ import annotations

from typing import Any

import httpx

from .config import settings


class CloudClient:
    def __init__(self) -> None:
        self.base = settings.cloud_base_url
        self.headers = {"Content-Type": "application/json"}
        if settings.agent_secret:
            self.headers["X-Agent-Secret"] = settings.agent_secret

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(f"{self.base}{path}", json=payload, headers=self.headers)
        try:
            data = r.json()
        except Exception:
            data = {"detail": r.text}
        if r.status_code >= 400:
            raise RuntimeError(f"{path} failed: {r.status_code} {data}")
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

