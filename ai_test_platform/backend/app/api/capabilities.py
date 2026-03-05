from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.credit_flow import add_credit_flow
from ..db import get_db
from ..models import CapabilityCallLog, CapabilityConfig, CapabilityPolicy, User
from .auth import _require_admin_token, get_current_user


router = APIRouter(prefix="/capabilities", tags=["capabilities"])


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


def _policy_match_user(row: CapabilityPolicy, user: User) -> bool:
    st = (row.subject_type or "").strip().lower()
    sv = (row.subject_value or "").strip()
    if st == "user_id":
        return sv.isdigit() and int(sv) == user.id
    if st == "email":
        return bool(user.email and user.email.lower() == sv.lower())
    return False


def _capability_allowed_for_user(db: Session, user: User, capability_id: str) -> bool:
    rules = (
        db.query(CapabilityPolicy)
        .filter(
            CapabilityPolicy.capability_id == capability_id,
            CapabilityPolicy.enabled.is_(True),
        )
        .all()
    )
    if not rules:
        return True
    matched_allow = False
    for r in rules:
        if not _policy_match_user(r, user):
            continue
        effect = (r.effect or "allow").strip().lower()
        if effect == "deny":
            return False
        if effect == "allow":
            matched_allow = True
    return matched_allow


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
