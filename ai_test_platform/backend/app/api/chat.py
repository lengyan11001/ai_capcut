"""对话接口：代理到 OpenClaw Gateway Chat Completions。

延迟主要来自：OpenClaw Gateway → 大模型推理（及可选 MCP 调用）。
优化方向：限制历史条数、Gateway 与后端同机/低延迟、开启流式（若 Gateway 支持）、选用更快模型。
计费：有 usage 时按 model_pricing 与 token 计费并写 usage_period；无 usage 时按固定积分 fallback。
用量限制：每用户每日次数上限 + 每分钟频率限制，防过度使用（前期内部用可放宽配置）。
"""
from __future__ import annotations

import logging
import re
import time
from collections import deque
from datetime import date, datetime, time as dt_time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func

from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.credit_flow import add_credit_flow
from ..core.credits import credits_for_chat
from ..core import model_pricing
from ..db import get_db
from .auth import get_current_user
from ..models import CreditFlow, OpenClawInstance, User, UserOpenClawBinding

logger = logging.getLogger(__name__)
router = APIRouter()

# 只保留最近 N 条历史，减少上下文长度以降低首 token 延迟
MAX_HISTORY_MESSAGES = 20

# 每分钟限流：每用户一个 deque 记录最近请求时间戳（进程内，多 worker 时每进程独立）
_chat_rate_limit_deques: Dict[int, deque] = {}
_RATE_LIMIT_WINDOW = 60.0  # 秒

_REDACT_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9]{10,}"), "[REDACTED_KEY]"),
    (re.compile(r"(api[_-]?key\s*[:=]\s*)([^\s,]+)", re.I), r"\1[REDACTED]"),
    (re.compile(r"((?:余额|积分|points?|credits?)\s*[:：]\s*)([0-9]+(?:\.[0-9]+)?)", re.I), r"\1[HIDDEN]"),
]
_REDACT_TERMS = ("速推", "fyshark", "ts-api.fyshark.com", "sutui_account", "account_id")


def _check_chat_rate_limit(user_id: int) -> bool:
    """返回 True 表示通过，False 表示超限应拒绝。"""
    cap = getattr(settings, "chat_rate_limit_per_minute", 0) or 0
    if cap <= 0:
        return True
    now = time.time()
    if user_id not in _chat_rate_limit_deques:
        _chat_rate_limit_deques[user_id] = deque(maxlen=cap + 1)
    d = _chat_rate_limit_deques[user_id]
    while d and d[0] < now - _RATE_LIMIT_WINDOW:
        d.popleft()
    if len(d) >= cap:
        return False
    d.append(now)
    return True


def _sanitize_reply(text: str) -> str:
    """兜底脱敏：隐藏供应商品牌、账号与密钥样式。"""
    out = text or ""
    for p, repl in _REDACT_PATTERNS:
        out = p.sub(repl, out)
    for term in _REDACT_TERMS:
        out = out.replace(term, "平台能力")
    return out


def _today_chat_count(db: Session, user_id: int) -> int:
    """当日已发生的智能对话扣费次数（related_type=chat）。"""
    start_of_today_utc = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.query(func.count(CreditFlow.id)).filter(
        CreditFlow.user_id == user_id,
        CreditFlow.related_type == "chat",
        CreditFlow.flow_type == "deduct",
        CreditFlow.created_at >= start_of_today_utc,
    ).scalar() or 0


class ChatMessage(BaseModel):
    role: str = Field(..., description="user | assistant | system")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    message: str = Field(..., description="当前用户输入")
    history: Optional[List[ChatMessage]] = Field(default_factory=list, description="多轮历史，用于会话上下文")


class ChatResponse(BaseModel):
    reply: str


def _is_learn_allowlist_user(user: User) -> bool:
    """当前用户是否在学习实例白名单内（仅白名单用户走带学习能力的主实例）。"""
    allowlist = (getattr(settings, "openclaw_learn_allowlist", None) or "").strip()
    if not allowlist:
        return False
    parts = [p.strip() for p in allowlist.split(",") if p.strip()]
    for p in parts:
        if p.isdigit() and int(p) == user.id:
            return True
        if p and getattr(user, "email", None) and user.email and p.lower() == user.email.lower():
            return True
    return False


def _resolve_openclaw_target(db: Session, user: User) -> tuple[str, str, str]:
    """
    返回 (base_url, token, agent_id)。
    - 白名单用户 -> 学习实例 + main
    - 已配置用户实例 -> 用户实例 + user_<id>
    - 否则（未配用户实例）-> 学习实例 + main（向后兼容）
    """
    url_learn = (getattr(settings, "openclaw_gateway_url", None) or "").strip().rstrip("/")
    token_learn = (getattr(settings, "openclaw_gateway_token", None) or "").strip()
    url_users = (getattr(settings, "openclaw_gateway_url_users", None) or "").strip().rstrip("/")
    token_users = (getattr(settings, "openclaw_gateway_token_users", None) or "").strip()

    if _is_learn_allowlist_user(user):
        if url_learn and token_learn:
            return url_learn, token_learn, "main"
        # 白名单但学习实例未配， fallback 到用户实例（若存在）
        if url_users and token_users:
            return url_users, token_users, f"user_{user.id}"
        return url_learn, token_learn, "main"

    # 优先按用户绑定实例池路由（注册后自动分配）
    binding = (
        db.query(UserOpenClawBinding)
        .filter(UserOpenClawBinding.user_id == user.id)
        .first()
    )
    if binding and binding.status == "assigned":
        ins = db.query(OpenClawInstance).filter(OpenClawInstance.id == binding.instance_id).first()
        if ins and ins.enabled:
            pool_url = (ins.base_url or "").strip().rstrip("/")
            pool_token = (ins.gateway_token or "").strip()
            pool_agent = (binding.agent_id or ins.default_agent_id or "main").strip() or "main"
            if pool_url and pool_token:
                return pool_url, pool_token, pool_agent

    if url_users and token_users:
        return url_users, token_users, f"user_{user.id}"
    # 未配用户实例：所有人走单一 Gateway（向后兼容）
    return url_learn, token_learn, "main"


def _openclaw_available(db: Session, user: Optional[User] = None) -> bool:
    """当前请求是否可用的 OpenClaw：按用户解析目标后检查 URL 与 token。"""
    if user is None:
        # 无用户时只检查是否至少有一个实例配置（用于文档/健康检查等）
        url_learn = (getattr(settings, "openclaw_gateway_url", None) or "").strip()
        token_learn = (getattr(settings, "openclaw_gateway_token", None) or "").strip()
        url_users = (getattr(settings, "openclaw_gateway_url_users", None) or "").strip()
        token_users = (getattr(settings, "openclaw_gateway_token_users", None) or "").strip()
        return bool(
            (url_learn and token_learn) or (url_users and token_users)
        )
    base, token, _ = _resolve_openclaw_target(db, user)
    return bool(base and token)


@router.post("/chat", response_model=ChatResponse, summary="智能对话（OpenClaw）")
async def chat_endpoint(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """将用户消息与历史转发到 OpenClaw Gateway 的 Chat Completions；每轮扣积分。"""
    # 每分钟频率限制
    if not _check_chat_rate_limit(current_user.id):
        cap = getattr(settings, "chat_rate_limit_per_minute", 0) or 0
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"请求过于频繁，每分钟最多 {cap} 次智能对话，请稍后再试",
        )
    # 每日次数上限
    daily_cap = getattr(settings, "chat_daily_cap_per_user", 0) or 0
    if daily_cap > 0:
        today_count = _today_chat_count(db, current_user.id)
        if today_count >= daily_cap:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"今日智能对话次数已达上限（{daily_cap} 次），明天再试",
            )
    need = credits_for_chat()
    if current_user.credits < need:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"积分不足，智能对话每轮需 {need} 积分，当前 {current_user.credits}，请充值后再试",
        )
    if not _openclaw_available(db, current_user):
        reply = (
            f"你说的是：{payload.message}\n\n"
            "当前未启用智能对话或你的账号暂无可用实例。\n"
            "请联系管理员配置 OpenClaw 或用户实例。"
        )
        return ChatResponse(reply=reply)
    base, token, agent_id = _resolve_openclaw_target(db, current_user)
    url = f"{base}/v1/chat/completions"
    messages = []
    history = payload.history or []
    for m in history:
        if m.role in ("user", "assistant", "system") and (m.content or "").strip():
            messages.append({"role": m.role, "content": (m.content or "").strip()})
    if len(messages) > MAX_HISTORY_MESSAGES:
        messages = messages[-MAX_HISTORY_MESSAGES:]
    messages.append({"role": "user", "content": payload.message})
    body = {
        "model": "openclaw",
        "messages": messages,
        "stream": False,
    }
    req_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "x-openclaw-agent-id": agent_id,
    }
    try:
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=body, headers=req_headers)
        duration_ms = round((time.perf_counter() - t0) * 1000)
        logger.info("openclaw_chat duration_ms=%s status=%s agent_id=%s", duration_ms, resp.status_code, agent_id)
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
        reply = _sanitize_reply(msg.get("content") or "")
        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        model_id = (data.get("model") or "").strip() or "openclaw:default"
        if not model_id or ":" not in model_id:
            model_id = "openclaw:default"
        if prompt_tokens or completion_tokens:
            need = model_pricing.compute_credits(db, model_id, prompt_tokens, completion_tokens)
        if need <= 0:
            need = credits_for_chat()
        user = db.query(User).filter(User.id == current_user.id).first()
        if user:
            add_credit_flow(db, user, "deduct", need, "智能对话", "chat", None)
            total_tokens = prompt_tokens + completion_tokens
            if total_tokens > 0:
                period_start = date.today().replace(day=1)
                model_pricing.add_usage_period(db, user.id, model_id, period_start, total_tokens)
            db.commit()
        out = ChatResponse(reply=reply.strip() or "（无回复内容）")
        return JSONResponse(
            content=out.model_dump(),
            headers={"X-OpenClaw-Duration-Ms": str(duration_ms)},
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"无法连接 OpenClaw Gateway: {e!s}",
        ) from e
