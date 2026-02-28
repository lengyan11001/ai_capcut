"""对话接口：代理到 OpenClaw Gateway Chat Completions。"""
from typing import Any, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..core.config import settings
from .auth import get_current_user
from ..models import User


router = APIRouter()


class ChatMessage(BaseModel):
    role: str = Field(..., description="user | assistant | system")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    message: str = Field(..., description="当前用户输入")
    history: Optional[List[ChatMessage]] = Field(default_factory=list, description="多轮历史，用于会话上下文")


class ChatResponse(BaseModel):
    reply: str


def _openclaw_available() -> bool:
    return bool(
        settings.openclaw_gateway_url
        and settings.openclaw_gateway_token
        and settings.openclaw_gateway_url.strip().rstrip("/")
    )


@router.post("/chat", response_model=ChatResponse, summary="智能对话（OpenClaw）")
async def chat_endpoint(payload: ChatRequest, current_user: User = Depends(get_current_user)):
    """将用户消息与历史转发到 OpenClaw Gateway 的 Chat Completions。"""
    if _openclaw_available():
        base = settings.openclaw_gateway_url.strip().rstrip("/")
        url = f"{base}/v1/chat/completions"
        messages: List[dict[str, Any]] = []
        for m in payload.history or []:
            if m.role in ("user", "assistant", "system") and (m.content or "").strip():
                messages.append({"role": m.role, "content": (m.content or "").strip()})
        messages.append({"role": "user", "content": payload.message})
        body = {
            "model": "openclaw",
            "messages": messages,
            "stream": False,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.openclaw_gateway_token}",
            "x-openclaw-agent-id": "main",
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(url, json=body, headers=headers)
            if resp.status_code != 200:
                detail = resp.text
                try:
                    j = resp.json()
                    detail = j.get("error", {}).get("message", detail) or detail
                except Exception:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"OpenClaw Gateway 返回 {resp.status_code}: {detail[:500]}",
                )
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="OpenClaw 未返回有效回复",
                )
            msg = choices[0].get("message") or {}
            reply = msg.get("content") or ""
            return ChatResponse(reply=reply.strip() or "（无回复内容）")
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"无法连接 OpenClaw Gateway: {e!s}",
            ) from e
    # 未启用智能对话时返回占位说明
    reply = (
        f"你说的是：{payload.message}\n\n"
        "当前未启用智能对话。\n"
        "请联系管理员启用 OpenClaw 服务后再试。"
    )
    return ChatResponse(reply=reply)
