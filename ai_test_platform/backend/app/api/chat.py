"""对话接口：代理到 OpenClaw Gateway Chat Completions。

延迟主要来自：OpenClaw Gateway → 大模型推理（及可选 MCP 调用）。
优化方向：限制历史条数、Gateway 与后端同机/低延迟、开启流式（若 Gateway 支持）、选用更快模型。
计费：有 usage 时按 model_pricing 与 token 计费并写 usage_period；无 usage 则不扣费。
用量限制：每用户每日次数上限 + 每分钟频率限制，防过度使用（前期内部用可放宽配置）。
"""
from __future__ import annotations

import logging
import json
import os
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
from ..core import model_pricing
from ..db import get_db
from .auth import get_current_user, oauth2_scheme
from ..models import CapabilityCallLog, CapabilityConfig, ChatTurnLog, CreditFlow, OpenClawInstance, User, UserOpenClawBinding

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
_IMAGE_INTENT_RE = re.compile(r"(生成|画|做).{0,8}(图|图片|海报|头像|插画)|文生图|出图|做一张图", re.I)
_IMAGE_UNAVAILABLE_RE = re.compile(r"(无法|不能|暂时).*?(生成|出).*?(图|图片)|没有可用.*?(图像|图片).*?能力", re.I)
_IMAGE_MODEL_QUERY_INTENT_RE = re.compile(r"(哪些|什么|可用|支持|列表|查询|看看|有哪).{0,12}(模型|model).{0,8}(生成|出).{0,8}(图|图片)", re.I)
_SUTUI_CREDIT_INTENT_RE = re.compile(r"(速推|sutui).{0,8}(积分|余额|点数|剩余)|查询.{0,8}(速推|sutui).{0,8}(积分|余额|点数)", re.I)


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


def _is_image_intent(text: str) -> bool:
    t = (text or "").strip()
    # “查询有哪些图片模型”属于咨询/查询意图，不应被当成“立即生成图片”。
    if t and _IMAGE_MODEL_QUERY_INTENT_RE.search(t):
        return False
    return bool(t and _IMAGE_INTENT_RE.search(t))


def _looks_like_image_unavailable_reply(text: str) -> bool:
    t = (text or "").strip()
    return bool(t and _IMAGE_UNAVAILABLE_RE.search(t))


def _is_sutui_credit_intent(text: str) -> bool:
    t = (text or "").strip()
    return bool(t and _SUTUI_CREDIT_INTENT_RE.search(t))


def _is_admin_user(user: User) -> bool:
    role = (getattr(user, "role", "") or "").strip().lower()
    return role == "admin"


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
    session_id: Optional[str] = Field(default=None, description="前端会话 ID，用于归档")
    context_id: Optional[str] = Field(default=None, description="上下文能力 ID（如 image.generate / stock.analysis）")


class ChatResponse(BaseModel):
    reply: str


def _add_chat_turn_log(
    db: Session,
    user_id: int,
    user_message: str,
    assistant_reply: str,
    session_id: Optional[str],
    context_id: Optional[str],
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """记录一条对话归档，不影响主流程可用性。"""
    row = ChatTurnLog(
        user_id=user_id,
        session_id=(session_id or "")[:128] or None,
        context_id=(context_id or "")[:128] or None,
        user_message=(user_message or "")[:5000],
        assistant_reply=(assistant_reply or "")[:20000],
        meta=meta or {},
    )
    db.add(row)


def _load_capability_upstream_urls() -> Dict[str, str]:
    out: Dict[str, str] = {}
    raw = (settings.capability_upstream_urls_json or "").strip()
    if raw:
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(k, str) and isinstance(v, str) and v.strip():
                        out[k.strip()] = v.strip()
        except Exception:
            pass
    if "sutui" not in out and (settings.capability_sutui_mcp_url or "").strip():
        out["sutui"] = (settings.capability_sutui_mcp_url or "").strip()
    # 向后兼容：直接从环境变量读取
    if not out:
        env_raw = os.environ.get("CAPABILITY_UPSTREAM_URLS_JSON", "").strip()
        if env_raw:
            try:
                obj = json.loads(env_raw)
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if isinstance(k, str) and isinstance(v, str) and v.strip():
                            out[k.strip()] = v.strip()
            except Exception:
                pass
    if "sutui" not in out and os.environ.get("CAPABILITY_SUTUI_MCP_URL", "").strip():
        out["sutui"] = os.environ.get("CAPABILITY_SUTUI_MCP_URL", "").strip()
    return out


async def _call_upstream_mcp_tool(server_url: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """调用上游 MCP HTTP 工具（initialize + tools/call）。"""
    async with httpx.AsyncClient(timeout=90.0) as client:
        init_body = {
            "jsonrpc": "2.0",
            "id": "init-chat-fallback",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "ai-test-platform-chat-fallback", "version": "0.1.0"},
            },
        }
        init_resp = await client.post(server_url, json=init_body)
        session_id = (
            init_resp.headers.get("Mcp-Session-Id")
            or init_resp.headers.get("mcp-session-id")
            or ""
        )
        call_body = {
            "jsonrpc": "2.0",
            "id": "call-chat-fallback",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        headers = {"Mcp-Session-Id": session_id} if session_id else {}
        r = await client.post(server_url, json=call_body, headers=headers)
        try:
            return r.json()
        except Exception:
            return {"error": {"message": f"Upstream MCP 返回非 JSON: status={r.status_code}"}}


def _extract_text_json(response: Dict[str, Any]) -> Dict[str, Any]:
    """从 MCP result.content[0].text 中解析 JSON。"""
    if not isinstance(response, dict):
        return {}
    result = response.get("result")
    if not isinstance(result, dict):
        return {}
    content = result.get("content")
    if not isinstance(content, list) or not content:
        return {}
    first = content[0]
    if not isinstance(first, dict):
        return {}
    text = first.get("text")
    if not isinstance(text, str):
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _extract_actual_credits(value: Any) -> Optional[int]:
    if isinstance(value, dict):
        for key in ("credits_charged", "cost_credits", "charged_credits", "actual_credits"):
            v = value.get(key)
            if isinstance(v, (int, float)) and v > 0:
                return int(v)
        for _, v in value.items():
            found = _extract_actual_credits(v)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _extract_actual_credits(item)
            if found is not None:
                return found
    return None


def _extract_should_charge(value: Any) -> bool:
    if isinstance(value, dict):
        for key in ("should_charge", "charged", "cost_incurred", "has_cost"):
            if key in value:
                v = value.get(key)
                if isinstance(v, bool):
                    return v
                if isinstance(v, (int, float)):
                    return v > 0
                if isinstance(v, str):
                    return v.strip().lower() in ("1", "true", "yes", "charged")
        cost = _extract_actual_credits(value)
        if cost is not None and cost > 0:
            return True
    return False


async def _try_image_generation_fallback(
    db: Session,
    current_user: User,
    payload: ChatRequest,
) -> Optional[str]:
    """
    当会话层未触发工具时，后端直接兜底调用 image.generate。
    返回成功文案或 None（表示兜底失败/不适用）。
    """
    cap = (
        db.query(CapabilityConfig)
        .filter(CapabilityConfig.capability_id == "image.generate", CapabilityConfig.enabled.is_(True))
        .first()
    )
    if not cap:
        return None
    upstream_urls = _load_capability_upstream_urls()
    upstream_url = upstream_urls.get((cap.upstream or "sutui").strip(), "").strip()
    if not upstream_url:
        return None
    default_model = os.environ.get("CAPABILITY_IMAGE_DEFAULT_MODEL", "jimeng-4.0").strip() or "jimeng-4.0"
    tool_args = {"prompt": payload.message, "model": default_model}
    t0 = time.perf_counter()
    upstream_resp = await _call_upstream_mcp_tool(upstream_url, cap.upstream_tool, tool_args)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    parsed = _extract_text_json(upstream_resp)
    success = bool(parsed.get("success"))
    err = str(parsed.get("error") or "")[:1000] or None
    should_charge = _extract_should_charge(upstream_resp)
    actual_credits = _extract_actual_credits(upstream_resp) or 0
    charged = 0
    if success and should_charge and actual_credits > 0:
        if current_user.credits >= actual_credits:
            charged = actual_credits
            add_credit_flow(db, current_user, "deduct", charged, f"能力调用：{cap.capability_id}", "capability_call", None)
    log = CapabilityCallLog(
        user_id=current_user.id,
        capability_id=cap.capability_id,
        upstream=cap.upstream,
        upstream_tool=cap.upstream_tool,
        success=success,
        credits_charged=charged,
        latency_ms=latency_ms,
        request_payload=tool_args,
        response_payload=upstream_resp if isinstance(upstream_resp, dict) else {"raw": str(upstream_resp)},
        error_message=err,
        source="chat_fallback",
        chat_session_id=(payload.session_id or "")[:128] or None,
        chat_context_id="image.generate",
    )
    db.add(log)
    if not success:
        db.commit()
        return None
    urls = [str(x).strip() for x in (parsed.get("urls") if isinstance(parsed.get("urls"), list) else []) if str(x).strip()]
    if not urls:
        db.commit()
        return None
    provider = str(parsed.get("provider") or cap.upstream or "sutui").strip() or "sutui"
    model_used = str(parsed.get("model") or default_model).strip() or default_model
    media_type = str(parsed.get("media_type") or "image").strip() or "image"
    lines = [
        "图片已生成成功。",
        f"- 来源能力: {cap.capability_id}",
        f"- 上游渠道: {provider}",
        f"- 使用模型: {model_used}",
        f"- 媒体类型: {media_type}",
    ]
    # 兼容两种口径：上游实际消耗（若返回）与平台实际扣费（本次记账）。
    if should_charge:
        lines.append(f"- 上游消耗: {actual_credits}")
    else:
        lines.append("- 上游消耗: 0")
    lines.append(f"- 平台扣费: {charged}")
    lines.append(f"- 生成耗时: {latency_ms}ms")
    lines.append("图片链接:")
    for idx, u in enumerate(urls, 1):
        lines.append(f"{idx}. {u}")
    reply = "\n".join(lines)
    _add_chat_turn_log(
        db=db,
        user_id=current_user.id,
        user_message=payload.message,
        assistant_reply=reply,
        session_id=payload.session_id,
        context_id=payload.context_id or "image.generate",
        meta={"fallback": "image.generate", "charged_credits": charged},
    )
    db.commit()
    return reply


async def _try_sutui_account_fallback(
    db: Session,
    current_user: User,
    payload: ChatRequest,
) -> Optional[str]:
    """管理员查询速推账户积分/余额时，直连 sutui.account 能力。"""
    if not _is_admin_user(current_user):
        return None
    cap = (
        db.query(CapabilityConfig)
        .filter(CapabilityConfig.capability_id == "sutui.account", CapabilityConfig.enabled.is_(True))
        .first()
    )
    upstream = (cap.upstream if cap else "sutui") or "sutui"
    upstream_tool = (cap.upstream_tool if cap else "account") or "account"
    upstream_urls = _load_capability_upstream_urls()
    upstream_url = upstream_urls.get(upstream.strip(), "").strip()
    if not upstream_url:
        return None
    t0 = time.perf_counter()
    upstream_resp = await _call_upstream_mcp_tool(upstream_url, upstream_tool, {})
    latency_ms = int((time.perf_counter() - t0) * 1000)
    parsed = _extract_text_json(upstream_resp)
    success = bool(parsed.get("success", True))
    err = str(parsed.get("error") or "")[:1000] or None
    log = CapabilityCallLog(
        user_id=current_user.id,
        capability_id="sutui.account",
        upstream=upstream,
        upstream_tool=upstream_tool,
        success=success,
        credits_charged=0,
        latency_ms=latency_ms,
        request_payload={},
        response_payload=upstream_resp if isinstance(upstream_resp, dict) else {"raw": str(upstream_resp)},
        error_message=err,
        source="chat_fallback",
        chat_session_id=(payload.session_id or "")[:128] or None,
        chat_context_id=payload.context_id or "sutui.account",
    )
    db.add(log)
    if not success:
        db.commit()
        return None
    key_lines: List[str] = []
    for k in ("balance", "credits", "points", "remaining", "remaining_credits"):
        if k in parsed:
            key_lines.append(f"- {k}: {parsed.get(k)}")
    if not key_lines:
        key_lines.append("- 明细: " + json.dumps(parsed, ensure_ascii=False)[:2000])
    reply = "速推账户信息如下：\n" + "\n".join(key_lines)
    _add_chat_turn_log(
        db=db,
        user_id=current_user.id,
        user_message=payload.message,
        assistant_reply=reply,
        session_id=payload.session_id,
        context_id=payload.context_id or "sutui.account",
        meta={"fallback": "sutui.account", "charged_credits": 0},
    )
    db.commit()
    return reply


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
    raw_token: str = Depends(oauth2_scheme),
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
    need = 0
    if not _openclaw_available(db, current_user):
        reply = (
            f"你说的是：{payload.message}\n\n"
            "当前未启用智能对话或你的账号暂无可用实例。\n"
            "请联系管理员配置 OpenClaw 或用户实例。"
        )
        _add_chat_turn_log(
            db=db,
            user_id=current_user.id,
            user_message=payload.message,
            assistant_reply=reply,
            session_id=payload.session_id,
            context_id=payload.context_id,
            meta={"type": "unavailable"},
        )
        db.commit()
        return ChatResponse(reply=reply)
    # 管理员查询速推积分/余额时，优先直连 sutui.account 能力。
    if _is_sutui_credit_intent(payload.message):
        user = db.query(User).filter(User.id == current_user.id).first()
        if user:
            account_reply = await _try_sutui_account_fallback(db, user, payload)
            if account_reply:
                return JSONResponse(
                    content=ChatResponse(reply=account_reply).model_dump(),
                    headers={"X-Chat-Fallback": "sutui.account"},
                )
    # 图片请求优先走统一能力路由，确保由速推链路执行真实出图。
    if _is_image_intent(payload.message):
        user = db.query(User).filter(User.id == current_user.id).first()
        if user:
            fallback_reply = await _try_image_generation_fallback(db, user, payload)
            if fallback_reply:
                return JSONResponse(
                    content=ChatResponse(reply=fallback_reply).model_dump(),
                    headers={"X-Chat-Fallback": "image.generate"},
                )
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
        # 透传真实用户身份，供 Gateway/MCP 按用户授权能力列表。
        "x-user-authorization": f"Bearer {raw_token}",
        "x-user-id": str(current_user.id),
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
        if need < 0:
            need = 0
        user = db.query(User).filter(User.id == current_user.id).first()
        if user:
            if need > 0 and user.credits < need:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=f"积分不足，本次对话需 {need} 积分，当前 {user.credits}，请充值后再试",
                )
            if need > 0:
                add_credit_flow(db, user, "deduct", need, "智能对话", "chat", None)
            total_tokens = prompt_tokens + completion_tokens
            if total_tokens > 0:
                period_start = date.today().replace(day=1)
                model_pricing.add_usage_period(db, user.id, model_id, period_start, total_tokens)
            # 图片场景兜底：若会话层回复“图片能力不可用”，自动改走统一能力 image.generate
            if _is_image_intent(payload.message) and _looks_like_image_unavailable_reply(reply):
                fallback_reply = await _try_image_generation_fallback(db, user, payload)
                if fallback_reply:
                    return JSONResponse(
                        content=ChatResponse(reply=fallback_reply).model_dump(),
                        headers={"X-OpenClaw-Duration-Ms": str(duration_ms), "X-Chat-Fallback": "image.generate"},
                    )
            _add_chat_turn_log(
                db=db,
                user_id=current_user.id,
                user_message=payload.message,
                assistant_reply=reply.strip() or "（无回复内容）",
                session_id=payload.session_id,
                context_id=payload.context_id,
                meta={
                    "model_id": model_id,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "charged_credits": need,
                },
            )
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


@router.get("/chat/history", summary="我的智能会话归档（可按能力上下文筛选）")
def list_chat_history(
    context_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(ChatTurnLog).filter(ChatTurnLog.user_id == current_user.id)
    if context_id:
        q = q.filter(ChatTurnLog.context_id == context_id)
    rows = (
        q.order_by(ChatTurnLog.created_at.desc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 500))
        .all()
    )
    return [
        {
            "id": r.id,
            "session_id": r.session_id,
            "context_id": r.context_id,
            "user_message": r.user_message,
            "assistant_reply": r.assistant_reply,
            "meta": r.meta,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]
