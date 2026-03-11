from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.credit_flow import add_credit_flow
from ..db import SessionLocal, get_db
from ..models import CapabilityCallLog, CapabilityConfig, CapabilityPolicy, User
from .auth import _require_admin_token, get_current_user


router = APIRouter(prefix="/capabilities", tags=["capabilities"])

ADMIN_ONLY_CAPABILITIES = {"sutui.account"}


def _is_admin_user(user: User) -> bool:
    role = (getattr(user, "role", "") or "").strip().lower()
    return role == "admin"


class CapabilityConfigIn(BaseModel):
    capability_id: str
    description: str
    upstream: str = "sutui"
    upstream_tool: str
    arg_schema: Optional[Dict[str, Any]] = None
    enabled: bool = True
    is_default: bool = False
    unit_credits: int = Field(default=0, ge=0)


class CapabilityConfigUpdate(BaseModel):
    description: Optional[str] = None
    upstream: Optional[str] = None
    upstream_tool: Optional[str] = None
    arg_schema: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    is_default: Optional[bool] = None
    unit_credits: Optional[int] = Field(default=None, ge=0)


class CapabilityPolicyIn(BaseModel):
    capability_id: str
    subject_type: str = Field(..., description="user_id | email")
    subject_value: str
    effect: str = Field(default="allow", description="allow | deny")
    enabled: bool = True


class CapabilityPolicyUpdate(BaseModel):
    subject_type: Optional[str] = None
    subject_value: Optional[str] = None
    effect: Optional[str] = None
    enabled: Optional[bool] = None


class AssignUserCapabilitiesIn(BaseModel):
    user_id: int
    capability_ids: List[str] = Field(default_factory=list)
    effect: str = Field(default="allow", description="allow|deny")


class CapabilityCallRecordIn(BaseModel):
    capability_id: str
    success: bool = False
    latency_ms: Optional[int] = None
    request_payload: Optional[Dict[str, Any]] = None
    response_payload: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    should_charge: bool = True
    actual_credits: Optional[int] = Field(default=None, ge=0)
    source: Optional[str] = "ui"
    chat_session_id: Optional[str] = None
    chat_context_id: Optional[str] = None


class RedditComment2VideoSubmitIn(BaseModel):
    """提交 Reddit 评论转视频任务；不填则使用后端默认（全部板块、时间段内）。"""
    max_clips: Optional[int] = Field(default=None, ge=1, le=20, description="生成条数，不填则用后端默认")
    subreddits: Optional[List[str]] = Field(default=None, description="指定板块，如 ['ProgrammerHumor']；不填则全部")


def _policy_match_user(row: CapabilityPolicy, user: User) -> bool:
    st = (row.subject_type or "").strip().lower()
    sv = (row.subject_value or "").strip()
    if st == "user_id":
        return sv.isdigit() and int(sv) == user.id
    if st == "email":
        return bool(user.email and user.email.lower() == sv.lower())
    return False


def _has_any_user_policy(db: Session, user: User) -> bool:
    """用户是否存在任意启用中的能力策略（allow/deny 任一都算）。"""
    rows = db.query(CapabilityPolicy).filter(CapabilityPolicy.enabled.is_(True)).all()
    for r in rows:
        if _policy_match_user(r, user):
            return True
    return False


def _capability_allowed_for_user(db: Session, user: User, capability_id: str) -> bool:
    # 关键管理能力仅允许 admin 使用（硬限制，优先于策略表）。
    # 对 admin 永久放行，避免被普通白名单策略误伤。
    if capability_id in ADMIN_ONLY_CAPABILITIES:
        return _is_admin_user(user)
    rules = (
        db.query(CapabilityPolicy)
        .filter(
            CapabilityPolicy.capability_id == capability_id,
            CapabilityPolicy.enabled.is_(True),
        )
        .all()
    )
    has_user_policy = _has_any_user_policy(db, user)
    if not rules:
        # 当用户已经被配置过任何能力策略时，进入白名单模式：未配置该能力即不允许。
        return not has_user_policy
    matched_allow = False
    matched_policy = False
    for r in rules:
        if not _policy_match_user(r, user):
            continue
        matched_policy = True
        effect = (r.effect or "allow").strip().lower()
        if effect == "deny":
            return False
        if effect == "allow":
            matched_allow = True
    if matched_allow:
        return True
    # 该能力存在策略但用户未命中 allow 时：
    # - 若用户在白名单模式，则默认拒绝
    # - 否则保持兼容：默认允许
    if has_user_policy:
        return False
    return not matched_policy


def _serialize_capability(row: CapabilityConfig) -> Dict[str, Any]:
    return {
        "id": row.id,
        "capability_id": row.capability_id,
        "description": row.description,
        "upstream": row.upstream,
        "upstream_tool": row.upstream_tool,
        "arg_schema": row.arg_schema,
        "enabled": row.enabled,
        "is_default": row.is_default,
        "unit_credits": row.unit_credits,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


def _project_root() -> Path:
    # backend/app/api/capabilities.py -> ai_test_platform
    return Path(__file__).resolve().parents[3]


def _sanitize_slug(text: str) -> str:
    x = re.sub(r"[^a-zA-Z0-9._-]+", "_", (text or "").strip()).strip("._-").lower()
    return x or "custom"


def _read_catalog_file(path: Path) -> Dict[str, Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for capability_id, cfg in raw.items():
        if isinstance(capability_id, str) and isinstance(cfg, dict):
            out[capability_id.strip()] = cfg
    return out


def _load_capabilities_from_catalog_files() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    candidates: List[Path] = []
    custom_path = (settings.capability_catalog_path or "").strip()
    if custom_path:
        candidates.append(Path(custom_path))
    mcp_dir = _project_root() / "mcp"
    candidates.extend([
        mcp_dir / "capability_catalog.local.json",
        mcp_dir / "capability_catalog.json",
    ])
    for p in candidates:
        try:
            if p.exists():
                data = _read_catalog_file(p)
                if data:
                    out.update(data)
        except Exception:
            continue
    return out


def _normalize_upstream(server_dir_name: str, server_name: str) -> str:
    s = f"{server_dir_name} {server_name}".lower()
    if "sutui" in s or "速推" in server_name:
        return "sutui"
    return _sanitize_slug(server_dir_name or server_name or "custom")


def _load_capabilities_from_cursor_mcp_tools() -> Dict[str, Dict[str, Any]]:
    """
    从本机 Cursor MCP 描述中抽取能力。
    仅用于“管理员重扫能力目录”时的本地增强发现；若路径不存在会自动跳过。
    """
    out: Dict[str, Dict[str, Any]] = {}
    root = Path.home() / ".cursor" / "projects"
    if not root.exists():
        return out
    for tool_file in root.glob("*/mcps/*/tools/*.json"):
        try:
            server_dir = tool_file.parents[1]
            meta_file = server_dir / "SERVER_METADATA.json"
            server_name = ""
            if meta_file.exists():
                meta_raw = json.loads(meta_file.read_text(encoding="utf-8"))
                if isinstance(meta_raw, dict):
                    server_name = str(meta_raw.get("serverName") or "").strip()
            tool_raw = json.loads(tool_file.read_text(encoding="utf-8"))
            if not isinstance(tool_raw, dict):
                continue
            tool_name = str(tool_raw.get("name") or "").strip()
            if not tool_name:
                continue
            upstream = _normalize_upstream(server_dir.name, server_name)
            capability_id = f"{upstream}.{_sanitize_slug(tool_name)}"
            arg_schema = tool_raw.get("arguments")
            if not isinstance(arg_schema, dict):
                arg_schema = {"type": "object", "properties": {}}
            out[capability_id] = {
                "description": str(tool_raw.get("description") or capability_id).strip() or capability_id,
                "upstream": upstream,
                "upstream_tool": tool_name,
                "arg_schema": arg_schema,
                "enabled": True,
                "is_default": False,
                "unit_credits": 0,
            }
        except Exception:
            continue
    return out


@router.get("/available", summary="当前用户可用能力（已做策略过滤）")
def list_available_capabilities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(CapabilityConfig)
        .filter(CapabilityConfig.enabled.is_(True))
        .order_by(CapabilityConfig.capability_id.asc())
        .all()
    )
    out = []
    for row in rows:
        if _capability_allowed_for_user(db, current_user, row.capability_id):
            out.append(
                {
                    "capability_id": row.capability_id,
                    "description": row.description,
                    "upstream": row.upstream,
                    "upstream_tool": row.upstream_tool,
                    "arg_schema": row.arg_schema or {"type": "object", "properties": {}},
                    "is_default": row.is_default,
                    "unit_credits": row.unit_credits,
                }
            )
    return {"capabilities": out}


@router.get("/registry", summary="能力目录（管理端）")
def list_capability_registry(
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin_token),
):
    rows = db.query(CapabilityConfig).order_by(CapabilityConfig.capability_id.asc()).all()
    return [_serialize_capability(x) for x in rows]


@router.post("/registry", summary="新增能力（管理端）")
def create_capability_registry(
    payload: CapabilityConfigIn,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin_token),
):
    capability_id = payload.capability_id.strip()
    if not capability_id:
        raise HTTPException(status_code=400, detail="capability_id 不能为空")
    exists = db.query(CapabilityConfig).filter(CapabilityConfig.capability_id == capability_id).first()
    if exists:
        raise HTTPException(status_code=400, detail="能力已存在")
    row = CapabilityConfig(
        capability_id=capability_id,
        description=payload.description.strip(),
        upstream=payload.upstream.strip() or "sutui",
        upstream_tool=payload.upstream_tool.strip(),
        arg_schema=payload.arg_schema,
        enabled=payload.enabled,
        is_default=payload.is_default,
        unit_credits=payload.unit_credits,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_capability(row)


@router.put("/registry/{capability_id}", summary="更新能力（管理端）")
def update_capability_registry(
    capability_id: str,
    payload: CapabilityConfigUpdate,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin_token),
):
    row = db.query(CapabilityConfig).filter(CapabilityConfig.capability_id == capability_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="能力不存在")
    if payload.description is not None:
        row.description = payload.description.strip()
    if payload.upstream is not None:
        row.upstream = payload.upstream.strip() or "sutui"
    if payload.upstream_tool is not None:
        row.upstream_tool = payload.upstream_tool.strip()
    if payload.arg_schema is not None:
        row.arg_schema = payload.arg_schema
    if payload.enabled is not None:
        row.enabled = payload.enabled
    if payload.is_default is not None:
        row.is_default = payload.is_default
    if payload.unit_credits is not None:
        row.unit_credits = payload.unit_credits
    db.commit()
    db.refresh(row)
    return _serialize_capability(row)


@router.get("/policies", summary="能力策略列表（管理端）")
def list_capability_policies(
    capability_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin_token),
):
    q = db.query(CapabilityPolicy)
    if capability_id:
        q = q.filter(CapabilityPolicy.capability_id == capability_id)
    rows = q.order_by(CapabilityPolicy.id.asc()).all()
    return [
        {
            "id": r.id,
            "capability_id": r.capability_id,
            "subject_type": r.subject_type,
            "subject_value": r.subject_value,
            "effect": r.effect,
            "enabled": r.enabled,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        }
        for r in rows
    ]


@router.post("/policies", summary="新增能力策略（管理端）")
def create_capability_policy(
    payload: CapabilityPolicyIn,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin_token),
):
    st = payload.subject_type.strip().lower()
    effect = payload.effect.strip().lower()
    if st not in ("user_id", "email"):
        raise HTTPException(status_code=400, detail="subject_type 仅支持 user_id/email")
    if effect not in ("allow", "deny"):
        raise HTTPException(status_code=400, detail="effect 仅支持 allow/deny")
    row = CapabilityPolicy(
        capability_id=payload.capability_id.strip(),
        subject_type=st,
        subject_value=payload.subject_value.strip(),
        effect=effect,
        enabled=payload.enabled,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.put("/policies/{policy_id}", summary="更新能力策略（管理端）")
def update_capability_policy(
    policy_id: int,
    payload: CapabilityPolicyUpdate,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin_token),
):
    row = db.query(CapabilityPolicy).filter(CapabilityPolicy.id == policy_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="策略不存在")
    if payload.subject_type is not None:
        st = payload.subject_type.strip().lower()
        if st not in ("user_id", "email"):
            raise HTTPException(status_code=400, detail="subject_type 仅支持 user_id/email")
        row.subject_type = st
    if payload.subject_value is not None:
        row.subject_value = payload.subject_value.strip()
    if payload.effect is not None:
        effect = payload.effect.strip().lower()
        if effect not in ("allow", "deny"):
            raise HTTPException(status_code=400, detail="effect 仅支持 allow/deny")
        row.effect = effect
    if payload.enabled is not None:
        row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    return {"id": row.id, "enabled": row.enabled}


@router.post("/record-call", summary="记录能力调用并按规则扣费（用户态）")
def record_capability_call(
    payload: CapabilityCallRecordIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cap = db.query(CapabilityConfig).filter(CapabilityConfig.capability_id == payload.capability_id).first()
    if not cap or not cap.enabled:
        raise HTTPException(status_code=404, detail="能力不存在或未启用")
    if not _capability_allowed_for_user(db, current_user, cap.capability_id):
        raise HTTPException(status_code=403, detail="能力未授权")

    credits = 0
    charge_amount = payload.actual_credits if payload.actual_credits is not None else cap.unit_credits
    if payload.should_charge and payload.success and charge_amount > 0:
        if current_user.credits < charge_amount:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"积分不足，调用该能力需 {charge_amount} 积分，当前 {current_user.credits}",
            )
        credits = charge_amount
        add_credit_flow(
            db,
            current_user,
            "deduct",
            credits,
            f"能力调用：{cap.capability_id}",
            "capability_call",
            None,
        )

    row = CapabilityCallLog(
        user_id=current_user.id,
        capability_id=cap.capability_id,
        upstream=cap.upstream,
        upstream_tool=cap.upstream_tool,
        success=payload.success,
        credits_charged=credits,
        latency_ms=payload.latency_ms,
        request_payload=payload.request_payload,
        response_payload=payload.response_payload,
        error_message=(payload.error_message or "")[:2000] or None,
        source=(payload.source or "ui")[:64],
        chat_session_id=(payload.chat_session_id or "")[:128] or None,
        chat_context_id=(payload.chat_context_id or "")[:128] or None,
    )
    db.add(row)
    db.commit()
    db.refresh(current_user)
    return {
        "detail": "ok",
        "credits_charged": credits,
        "credits_left": current_user.credits,
        "call_log_id": row.id,
    }


def _run_reddit_comment2video_job(call_log_id: int) -> None:
    """后台执行：调用 Reddit 后端 8003，完成后更新能力调用记录状态与结果。"""
    base_url = (getattr(settings, "reddit_comment2video_backend_url", None) or "").strip().rstrip("/")
    if not base_url:
        _update_call_log_status(call_log_id, "failed", success=False, error_message="未配置 reddit_comment2video_backend_url")
        return
    db = SessionLocal()
    req: Dict[str, Any] = {}
    try:
        row = db.query(CapabilityCallLog).filter(CapabilityCallLog.id == call_log_id).first()
        if not row:
            return
        req = dict(row.request_payload or {})
    finally:
        db.close()
    body: Dict[str, Any] = {}
    if req.get("max_clips") is not None:
        body["max_clips"] = int(req["max_clips"])
    if req.get("subreddits"):
        body["subreddits"] = list(req["subreddits"]) if isinstance(req["subreddits"], list) else [str(req["subreddits"])]
    import time
    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=600.0) as client:
            r = client.post(f"{base_url}/generate-clips", json=body if body else {"max_clips": 2})
            latency_ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            data = r.json() if r.content else {}
            _update_call_log_status(
                call_log_id,
                "completed",
                success=data.get("success", True),
                latency_ms=latency_ms,
                response_payload=data,
                error_message=data.get("error") or None,
            )
        else:
            _update_call_log_status(
                call_log_id,
                "failed",
                success=False,
                latency_ms=latency_ms,
                response_payload={"status_code": r.status_code, "text": (r.text or "")[:1000]},
                error_message=f"后端返回 {r.status_code}: {(r.text or '')[:500]}",
            )
    except Exception as e:  # noqa: BLE001
        _update_call_log_status(
            call_log_id,
            "failed",
            success=False,
            error_message=str(e)[:2000],
        )


def _update_call_log_status(
    call_log_id: int,
    status_value: str,
    success: bool = False,
    latency_ms: Optional[int] = None,
    response_payload: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> None:
    db = SessionLocal()
    try:
        row = db.query(CapabilityCallLog).filter(CapabilityCallLog.id == call_log_id).first()
        if row:
            row.status = status_value
            row.success = success
            if latency_ms is not None:
                row.latency_ms = latency_ms
            if response_payload is not None:
                row.response_payload = response_payload
            if error_message is not None:
                row.error_message = (error_message or "")[:2000] or None
            db.commit()
    finally:
        db.close()


REDDIT_CAPABILITY_ID = "skill.reddit_comment2video"

REDDIT_UNCONFIGURED_GUIDE = (
    "请先到 **能力库 → Reddit 评论转短视频** 页面，配置该板块与 YouTube 博主、背景视频/音频的对应关系后再生成。"
)


def _fetch_reddit_configured_subreddits() -> List[str]:
    """从 Reddit 后端 8003 拉取当前已配置的板块名称列表。"""
    base_url = (getattr(settings, "reddit_comment2video_backend_url", None) or "").strip().rstrip("/")
    if not base_url:
        return []
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{base_url}/configured-subreddits")
            if r.status_code == 200 and r.content:
                data = r.json()
                return list(data.get("subreddits") or [])
    except Exception:
        pass
    return []


@router.get("/reddit-comment2video/configured-subreddits", summary="查询当前已配置的 Reddit 板块（会话可用）")
def get_reddit_configured_subreddits(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回当前已配置的板块列表与数量，供会话中「配置了几个板块」类问题使用。"""
    cap = db.query(CapabilityConfig).filter(CapabilityConfig.capability_id == REDDIT_CAPABILITY_ID).first()
    if not cap or not cap.enabled:
        raise HTTPException(status_code=404, detail="能力不存在或未启用")
    if not _capability_allowed_for_user(db, current_user, cap.capability_id):
        raise HTTPException(status_code=403, detail="能力未授权")
    names = _fetch_reddit_configured_subreddits()
    return {"subreddits": names, "count": len(names)}


@router.post("/reddit-comment2video/submit", summary="提交 Reddit 评论转视频任务（异步）")
def submit_reddit_comment2video(
    payload: RedditComment2VideoSubmitIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建一条能力调用记录（状态=执行中），后台调用 8003 生成视频，完成后更新记录。用户可到能力库查看能力调用记录获取状态与下载链接。"""
    cap = db.query(CapabilityConfig).filter(CapabilityConfig.capability_id == REDDIT_CAPABILITY_ID).first()
    if not cap or not cap.enabled:
        raise HTTPException(status_code=404, detail="能力不存在或未启用")
    if not _capability_allowed_for_user(db, current_user, cap.capability_id):
        raise HTTPException(status_code=403, detail="能力未授权")
    base_url = (getattr(settings, "reddit_comment2video_backend_url", None) or "").strip().rstrip("/")
    if not base_url:
        raise HTTPException(status_code=503, detail="未配置 Reddit 评论转视频后端地址 reddit_comment2video_backend_url")

    if payload.subreddits:
        configured = _fetch_reddit_configured_subreddits()
        configured_lower = {s.strip().lower() for s in configured if s}
        missing = [s for s in payload.subreddits if (s or "").strip().lower() not in configured_lower]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"以下板块尚未配置：{', '.join(missing)}。{REDDIT_UNCONFIGURED_GUIDE}",
            )

    request_payload: Dict[str, Any] = {}
    if payload.max_clips is not None:
        request_payload["max_clips"] = payload.max_clips
    if payload.subreddits:
        request_payload["subreddits"] = payload.subreddits

    row = CapabilityCallLog(
        user_id=current_user.id,
        capability_id=REDDIT_CAPABILITY_ID,
        upstream=cap.upstream,
        upstream_tool=cap.upstream_tool,
        success=False,
        credits_charged=0,
        latency_ms=None,
        request_payload=request_payload or None,
        response_payload=None,
        error_message=None,
        source="mcp_invoke",
        chat_session_id=None,
        chat_context_id=REDDIT_CAPABILITY_ID,
        status="running",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    background_tasks.add_task(_run_reddit_comment2video_job, row.id)
    return {
        "call_log_id": row.id,
        "message": "任务已创建，请到能力库查看能力调用记录；完成的可查看下载链接，执行中或失败的会显示状态与原因。",
    }


@router.get("/my-call-logs", summary="我的能力调用记录（用户态）")
def list_my_capability_call_logs(
    capability_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(CapabilityCallLog).filter(CapabilityCallLog.user_id == current_user.id)
    if capability_id:
        q = q.filter(CapabilityCallLog.capability_id == capability_id)
    rows = (
        q.order_by(CapabilityCallLog.created_at.desc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 500))
        .all()
    )
    return [
        {
            "id": r.id,
            "capability_id": r.capability_id,
            "upstream": r.upstream,
            "upstream_tool": r.upstream_tool,
            "success": r.success,
            "credits_charged": r.credits_charged,
            "latency_ms": r.latency_ms,
            "request_payload": r.request_payload,
            "response_payload": r.response_payload,
            "error_message": r.error_message,
            "source": r.source,
            "chat_session_id": r.chat_session_id,
            "chat_context_id": r.chat_context_id,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "status": r.status,
        }
        for r in rows
    ]


@router.get("/call-logs", summary="能力调用审计（管理端）")
def list_capability_call_logs(
    user_id: Optional[int] = None,
    capability_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin_token),
):
    q = db.query(CapabilityCallLog)
    if user_id is not None:
        q = q.filter(CapabilityCallLog.user_id == user_id)
    if capability_id:
        q = q.filter(CapabilityCallLog.capability_id == capability_id)
    rows = (
        q.order_by(CapabilityCallLog.created_at.desc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 500))
        .all()
    )
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "capability_id": r.capability_id,
            "upstream": r.upstream,
            "upstream_tool": r.upstream_tool,
            "success": r.success,
            "credits_charged": r.credits_charged,
            "latency_ms": r.latency_ms,
            "request_payload": r.request_payload,
            "response_payload": r.response_payload,
            "error_message": r.error_message,
            "source": r.source,
            "chat_session_id": r.chat_session_id,
            "chat_context_id": r.chat_context_id,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "status": getattr(r, "status", None),
        }
        for r in rows
    ]


@router.get("/admin/registry", summary="能力目录（管理员Bearer）")
def admin_registry_bearer(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="admin only")
    rows = db.query(CapabilityConfig).order_by(CapabilityConfig.capability_id.asc()).all()
    return [_serialize_capability(x) for x in rows]


@router.post("/admin/registry/rescan", summary="管理员重扫并同步能力目录（Bearer）")
def admin_rescan_registry_bearer(
    include_cursor_mcp: bool = True,
    overwrite_existing: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="admin only")

    merged: Dict[str, Dict[str, Any]] = {}
    merged.update(_load_capabilities_from_catalog_files())
    if include_cursor_mcp:
        mcp_caps = _load_capabilities_from_cursor_mcp_tools()
        # 显式目录优先，MCP 自动发现仅补充缺失项
        for cid, cfg in mcp_caps.items():
            if cid not in merged:
                merged[cid] = cfg

    created = 0
    updated = 0
    ignored = 0
    for capability_id in sorted(merged.keys()):
        cfg = merged[capability_id] if isinstance(merged[capability_id], dict) else {}
        if not capability_id:
            ignored += 1
            continue

        row = db.query(CapabilityConfig).filter(CapabilityConfig.capability_id == capability_id).first()
        if not row:
            row = CapabilityConfig(
                capability_id=capability_id,
                description=str(cfg.get("description") or capability_id),
                upstream=str(cfg.get("upstream") or "sutui"),
                upstream_tool=str(cfg.get("upstream_tool") or "").strip(),
                arg_schema=cfg.get("arg_schema") if isinstance(cfg.get("arg_schema"), dict) else None,
                enabled=bool(cfg.get("enabled", True)),
                is_default=bool(cfg.get("is_default", False)),
                unit_credits=int(cfg.get("unit_credits") or 0),
            )
            db.add(row)
            created += 1
            continue

        if not overwrite_existing:
            ignored += 1
            continue

        row.description = str(cfg.get("description") or row.description or capability_id)
        row.upstream = str(cfg.get("upstream") or row.upstream or "sutui")
        row.upstream_tool = str(cfg.get("upstream_tool") or row.upstream_tool or "").strip()
        if isinstance(cfg.get("arg_schema"), dict):
            row.arg_schema = cfg.get("arg_schema")
        if "enabled" in cfg:
            row.enabled = bool(cfg.get("enabled"))
        if "is_default" in cfg:
            row.is_default = bool(cfg.get("is_default"))
        if "unit_credits" in cfg:
            try:
                row.unit_credits = int(cfg.get("unit_credits") or 0)
            except Exception:
                pass
        updated += 1

    db.commit()
    return {
        "detail": "ok",
        "created": created,
        "updated": updated,
        "ignored": ignored,
        "total_from_scan": len(merged),
    }


@router.get("/admin/policies", summary="能力策略列表（管理员Bearer）")
def admin_list_policies_bearer(
    capability_id: Optional[str] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="admin only")
    q = db.query(CapabilityPolicy)
    if capability_id:
        q = q.filter(CapabilityPolicy.capability_id == capability_id)
    if user_id is not None:
        q = q.filter(CapabilityPolicy.subject_type == "user_id", CapabilityPolicy.subject_value == str(user_id))
    rows = q.order_by(CapabilityPolicy.id.asc()).all()
    return [
        {
            "id": r.id,
            "capability_id": r.capability_id,
            "subject_type": r.subject_type,
            "subject_value": r.subject_value,
            "effect": r.effect,
            "enabled": r.enabled,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        }
        for r in rows
    ]


@router.post("/admin/assign-user", summary="管理员分配用户能力（Bearer，全量替换）")
def admin_assign_user_capabilities(
    payload: AssignUserCapabilitiesIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="admin only")
    effect = (payload.effect or "allow").strip().lower()
    if effect not in ("allow", "deny"):
        raise HTTPException(status_code=400, detail="effect 仅支持 allow/deny")

    # 删除该用户之前所有 user_id 规则后重建，保持可视化配置简单
    db.query(CapabilityPolicy).filter(
        CapabilityPolicy.subject_type == "user_id",
        CapabilityPolicy.subject_value == str(payload.user_id),
    ).delete()

    cap_ids = [str(x).strip() for x in payload.capability_ids if str(x).strip()]
    cap_set = set(cap_ids)
    if cap_set:
        exists_caps = db.query(CapabilityConfig.capability_id).filter(CapabilityConfig.capability_id.in_(cap_set)).all()
        exists_set = {x[0] for x in exists_caps}
        missing = sorted(cap_set - exists_set)
        if missing:
            raise HTTPException(status_code=400, detail=f"能力不存在: {', '.join(missing)}")
    for cap_id in cap_ids:
        db.add(
            CapabilityPolicy(
                capability_id=cap_id,
                subject_type="user_id",
                subject_value=str(payload.user_id),
                effect=effect,
                enabled=True,
            )
        )
    db.commit()
    return {"detail": "ok", "assigned_count": len(cap_ids)}


@router.post("/admin/registry", summary="管理员新增能力（Bearer）")
def admin_create_registry_bearer(
    payload: CapabilityConfigIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="admin only")
    capability_id = (payload.capability_id or "").strip()
    if not capability_id:
        raise HTTPException(status_code=400, detail="capability_id 不能为空")
    exists = db.query(CapabilityConfig).filter(CapabilityConfig.capability_id == capability_id).first()
    if exists:
        raise HTTPException(status_code=400, detail="能力已存在")
    row = CapabilityConfig(
        capability_id=capability_id,
        description=(payload.description or "").strip() or capability_id,
        upstream=(payload.upstream or "sutui").strip() or "sutui",
        upstream_tool=(payload.upstream_tool or "").strip(),
        arg_schema=payload.arg_schema,
        enabled=payload.enabled,
        is_default=payload.is_default,
        unit_credits=payload.unit_credits,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_capability(row)


@router.put("/admin/registry/{capability_id}", summary="管理员更新能力（Bearer）")
def admin_update_registry_bearer(
    capability_id: str,
    payload: CapabilityConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="admin only")
    row = db.query(CapabilityConfig).filter(CapabilityConfig.capability_id == capability_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="能力不存在")
    if payload.description is not None:
        row.description = payload.description.strip()
    if payload.upstream is not None:
        row.upstream = payload.upstream.strip() or "sutui"
    if payload.upstream_tool is not None:
        row.upstream_tool = payload.upstream_tool.strip()
    if payload.arg_schema is not None:
        row.arg_schema = payload.arg_schema
    if payload.enabled is not None:
        row.enabled = payload.enabled
    if payload.is_default is not None:
        row.is_default = payload.is_default
    if payload.unit_credits is not None:
        row.unit_credits = payload.unit_credits
    db.commit()
    db.refresh(row)
    return _serialize_capability(row)
