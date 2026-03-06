from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
import httpx
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db import get_db
from ..core.reddit_ai import analyze_risk, generate_strategy
from ..models import (
    ControlDispatchGroup,
    ControlAgent,
    ControlTask,
    MobileDevice,
    RedditAccountAsset,
    RedditStrategyConfig,
    RiskAnalysisReport,
    NurtureBinding,
    NurturePlan,
    NurtureScheduleItem,
    NurtureStrategySnapshot,
    TaskExecution,
    TaskExecutionLog,
    User,
    UserDeviceAssignment,
    UserRedditAccountAssignment,
)
from .auth import get_current_user


router = APIRouter(prefix="/group-control", tags=["group-control"])
logger = logging.getLogger(__name__)


def _iso(x: Optional[datetime]) -> Optional[str]:
    return x.isoformat() if x else None


def _build_fallback_plan(days: int) -> dict[str, Any]:
    schedule: list[dict[str, Any]] = []
    for day in range(1, max(days, 1) + 1):
        stage = "warmup" if day <= 7 else ("steady" if day <= 20 else "engage")
        seq = 0

        # Morning: profile_check (every day)
        seq += 1
        schedule.append({
            "day_no": day, "seq_no": seq, "hour": 9, "minute": 0,
            "stage": stage, "title": f"day{day:02d}-profile-check",
            "payload": {"action": "profile_check"},
        })

        # Mid-morning: browse or search
        seq += 1
        action = "browse" if day <= 5 else "search"
        p: dict[str, Any] = {"action": action, "duration_min": 8 if day <= 7 else 12}
        if action == "search":
            p["keyword"] = "trending"
        schedule.append({
            "day_no": day, "seq_no": seq, "hour": 10, "minute": 30,
            "stage": stage, "title": f"day{day:02d}-{action}",
            "payload": p,
        })

        # Afternoon: upvote (steady+) or subscribe (steady+)
        if day > 7:
            seq += 1
            if day % 3 == 0:
                schedule.append({
                    "day_no": day, "seq_no": seq, "hour": 15, "minute": 0,
                    "stage": stage, "title": f"day{day:02d}-subscribe",
                    "payload": {"action": "subscribe"},
                })
            else:
                schedule.append({
                    "day_no": day, "seq_no": seq, "hour": 15, "minute": 0,
                    "stage": stage, "title": f"day{day:02d}-upvote",
                    "payload": {"action": "upvote", "duration_min": 10, "max_actions": 15, "upvote_ratio": 0.04},
                })

        # Evening: browse
        seq += 1
        schedule.append({
            "day_no": day, "seq_no": seq, "hour": 20, "minute": 0,
            "stage": stage, "title": f"day{day:02d}-browse-evening",
            "payload": {"action": "browse", "duration_min": 8},
        })

    return {
        "plan_version": "v1",
        "summary": f"auto-generated {days}-day nurture plan (6 actions: browse/search/upvote/subscribe/comment/profile_check)",
        "plan_horizon_days": days,
        "next_review_in_days": 1,
        "schedule": schedule,
    }


def _call_openclaw_for_plan(
    user: User,
    binding: NurtureBinding,
    objective: str,
    risk_preference: str,
) -> Optional[dict[str, Any]]:
    # 优先使用云端 OpenClaw 生成计划；失败时返回 None，由 fallback 接管。
    from .chat import _resolve_openclaw_target
    from ..db import SessionLocal

    db2 = SessionLocal()
    try:
        base, token, agent_id = _resolve_openclaw_target(db2, user)
    except Exception:
        db2.close()
        return None
    finally:
        try:
            db2.close()
        except Exception:
            pass
    if not base or not token:
        return None
    prompt = (
        "你是 Reddit 养号计划器。输出严格 JSON，不要 markdown。\n"
        "目标：生成仅养号（不发帖）计划，字段必须包含 plan_version, summary, plan_horizon_days, next_review_in_days, schedule。\n"
        "schedule 每项字段必须包含 day_no, seq_no, hour, minute, stage, title, payload。\n"
        "payload 必须包含 action 字段，以及该 action 对应的参数。\n\n"
        "=== 可用动作目录（只能从以下 action 中选择）===\n"
        "- browse: 滑动浏览首页/热门 Feed | 可选参数: duration_min, max_scrolls | 适用阶段: warmup,steady,engage,post_ready | 风险: low\n"
        "- search: 搜索关键词并浏览结果 | 必选参数: keyword | 可选: duration_min, max_scrolls | 适用阶段: warmup,steady,engage,post_ready | 风险: low\n"
        "- upvote: 浏览 Feed 过程中按概率随机点赞 | 可选参数: duration_min, max_actions, upvote_ratio(0-1) | 适用阶段: steady,engage,post_ready | 风险: medium\n"
        "- subscribe: 进入指定/推荐 Subreddit 并 Join | 可选参数: subreddit_name | 适用阶段: steady,engage,post_ready | 风险: low\n"
        "- comment: 打开帖子发表简短评论 | 可选参数: max_actions, comment_templates(字符串数组) | 适用阶段: engage,post_ready | 风险: high\n"
        "- profile_check: 进入 Profile 页读取 karma 和账号状态 | 无参数 | 适用阶段: 所有 | 风险: low\n\n"
        "=== 编排约束 ===\n"
        "1. warmup 阶段(前7天)只允许 browse/search/profile_check\n"
        "2. steady 阶段(8-20天)可增加 upvote/subscribe，upvote_ratio 不超过 0.05\n"
        "3. engage 阶段(21天+)可增加 comment，每天最多 2 条评论\n"
        "4. 每天至少安排 1 次 profile_check\n"
        "5. 单次 session 持续时间 duration_min 建议 5-15 分钟\n"
        "6. plan_horizon_days 取 14-60 的整数，next_review_in_days 取 1-3\n\n"
        f"参数：objective={objective}, risk_preference={risk_preference}, current_phase={binding.phase}, "
        f"current_karma={binding.current_karma}, target_karma={binding.target_karma}, "
        f"account_health={binding.account_health}, mode={binding.automation_mode}。"
    )
    body = {
        "model": "openclaw",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-openclaw-agent-id": agent_id,
    }
    try:
        with httpx.Client(timeout=40.0) as client:
            resp = client.post(f"{base.rstrip('/')}/v1/chat/completions", headers=headers, json=body)
            if resp.status_code >= 300:
                return None
            data = resp.json() if resp.content else {}
            choices = data.get("choices") or []
            content = ""
            if choices and isinstance(choices[0], dict):
                msg = choices[0].get("message") or {}
                content = str(msg.get("content") or "")
            if not content.strip():
                return None
            raw = content.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-zA-Z]*", "", raw).strip()
                raw = raw[:-3].strip() if raw.endswith("```") else raw
            plan = json.loads(raw)
            if not isinstance(plan, dict):
                return None
            if not isinstance(plan.get("schedule"), list):
                return None
            return plan
    except Exception:
        return None


def _daily_strategy_scan_if_due(db: Session) -> Optional[NurtureStrategySnapshot]:
    today = datetime.utcnow().date()
    existed = (
        db.query(NurtureStrategySnapshot)
        .filter(NurtureStrategySnapshot.reviewed_date == today)
        .order_by(NurtureStrategySnapshot.id.desc())
        .first()
    )
    if existed:
        return existed

    since = datetime.utcnow() - timedelta(hours=24)
    total = (
        db.query(func.count(NurtureScheduleItem.id))
        .filter(NurtureScheduleItem.dispatched_at.is_not(None), NurtureScheduleItem.dispatched_at >= since)
        .scalar()
        or 0
    )
    failed = (
        db.query(func.count(NurtureScheduleItem.id))
        .filter(
            NurtureScheduleItem.dispatched_at.is_not(None),
            NurtureScheduleItem.dispatched_at >= since,
            NurtureScheduleItem.status.in_(["failed", "cancelled"]),
        )
        .scalar()
        or 0
    )
    fail_rate = (float(failed) / float(total)) if total else 0.0
    severity = "low"
    requires_reconfirm = False
    recommendations: dict[str, Any] = {
        "reduce_upvote_ratio_by": 0.0,
        "increase_cooldown_minutes": 0,
        "switch_mode": None,
    }
    if fail_rate >= 0.35:
        severity = "high"
        requires_reconfirm = True
        recommendations = {
            "reduce_upvote_ratio_by": 0.03,
            "increase_cooldown_minutes": 30,
            "switch_mode": "conservative",
        }
    elif fail_rate >= 0.2:
        severity = "medium"
        recommendations = {
            "reduce_upvote_ratio_by": 0.02,
            "increase_cooldown_minutes": 15,
            "switch_mode": "conservative",
        }
    summary = (
        f"daily strategy review total={total}, failed={failed}, fail_rate={fail_rate:.2f}, "
        f"severity={severity}, requires_reconfirm={requires_reconfirm}"
    )
    snap = NurtureStrategySnapshot(
        reviewed_date=today,
        source="openclaw_or_fallback",
        severity=severity,
        summary=summary,
        recommendations=recommendations,
        requires_reconfirm=requires_reconfirm,
    )
    db.add(snap)
    if requires_reconfirm:
        rows = (
            db.query(NurturePlan)
            .filter(NurturePlan.status.in_(["approved", "active"]))
            .all()
        )
        for p in rows:
            p.requires_reconfirm = True
            p.last_review_at = datetime.utcnow()
            p.next_review_at = datetime.utcnow() + timedelta(days=1)
            db.add(p)
    db.commit()
    db.refresh(snap)
    return snap


def _dispatch_due_nurture_items(db: Session) -> int:
    _daily_strategy_scan_if_due(db)
    now = datetime.utcnow()
    due = (
        db.query(NurtureScheduleItem)
        .filter(
            NurtureScheduleItem.status == "scheduled",
            NurtureScheduleItem.scheduled_at <= now,
        )
        .order_by(NurtureScheduleItem.scheduled_at.asc(), NurtureScheduleItem.id.asc())
        .all()
    )
    dispatched = 0
    for item in due:
        plan = db.query(NurturePlan).filter(NurturePlan.id == item.plan_id).first()
        binding = db.query(NurtureBinding).filter(NurtureBinding.id == item.binding_id).first()
        if not plan or plan.status not in {"approved", "active"} or not binding:
            item.status = "skipped"
            item.last_error_code = "plan_inactive_or_binding_missing"
            item.last_error_message = "plan inactive or binding missing"
            item.finished_at = now
            db.add(item)
            continue
        if bool(getattr(plan, "requires_reconfirm", False)):
            continue
        if binding.status != "active":
            item.status = "skipped"
            item.last_error_code = "binding_inactive"
            item.last_error_message = f"binding status={binding.status}"
            item.finished_at = now
            db.add(item)
            continue
        if item.stage == "post_ready" and not binding.eligible_for_posting:
            # 尚未达标，不放行发帖阶段，顺延 24h 再检查
            item.scheduled_at = item.scheduled_at + timedelta(hours=24)
            db.add(item)
            continue
        task_payload = dict(item.payload or {})
        task_payload["reddit_account_id"] = binding.reddit_account_id
        row = ControlTask(
            user_id=item.user_id,
            title=item.title,
            platform="reddit",
            task_type="reddit_flow",
            payload=task_payload,
            target_device_id=binding.device_id,
            target_account_id=binding.reddit_account_id,
            priority=45,
            max_retries=1,
            status="pending",
            nurture_schedule_item_id=item.id,
        )
        db.add(row)
        db.flush()
        item.control_task_id = row.id
        item.dispatched_at = now
        item.status = "dispatched"
        db.add(item)
        if plan.status == "approved":
            plan.status = "active"
            plan.start_at = plan.start_at or now
            db.add(plan)
        dispatched += 1
    if due:
        db.commit()
    return dispatched


class DeviceStateIn(BaseModel):
    serial: str
    alias: Optional[str] = None
    platform: str = "android"
    adb_status: str = "device"
    appium_status: str = "unknown"
    meta: Optional[dict[str, Any]] = None
    account_attrs: Optional[dict[str, Any]] = None  # niche, phase, karma, tags 等


class AgentRegisterIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    agent_key: str = Field(..., min_length=3, max_length=255)
    host: Optional[str] = None
    labels: Optional[dict[str, Any]] = None
    devices: list[DeviceStateIn] = Field(default_factory=list)


class AgentHeartbeatIn(BaseModel):
    host: Optional[str] = None
    labels: Optional[dict[str, Any]] = None
    devices: list[DeviceStateIn] = Field(default_factory=list)


class DeviceFilterIn(BaseModel):
    niche: Optional[str] = None  # fashion|3c|beauty|pet|general
    min_phase: Optional[str] = None  # nurture_phase_1|phase_2|post_ready
    min_karma: Optional[int] = None
    tags: Optional[list[str]] = None  # 需包含任一标签


class CreateTaskIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    platform: str = Field(default="reddit")
    task_type: str = Field(default="reddit_flow")
    payload: dict[str, Any] = Field(default_factory=dict)
    target_device_id: Optional[int] = None
    target_device_ids: Optional[list[int]] = None
    target_account_id: Optional[int] = None
    target_account_ids: Optional[list[int]] = None
    target_group_id: Optional[int] = None
    device_filter: Optional[dict[str, Any]] = None  # niche, min_phase, min_karma, tags
    priority: int = Field(default=50, ge=0, le=100)
    max_retries: int = Field(default=0, ge=0, le=10)


class AgentPollIn(BaseModel):
    device_serials: list[str] = Field(default_factory=list)


class ExecutionLogIn(BaseModel):
    level: str = "info"
    message: str
    screenshot_url: Optional[str] = None
    payload: Optional[dict[str, Any]] = None


class TaskReportIn(BaseModel):
    execution_id: Optional[int] = None
    status: str = Field(..., description="running|success|failed|cancelled")
    step: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metrics: Optional[dict[str, Any]] = None
    logs: list[ExecutionLogIn] = Field(default_factory=list)


def _ensure_agent_secret(x_agent_secret: Optional[str]) -> None:
    configured = (settings.control_agent_secret or "").strip()
    if configured and x_agent_secret != configured:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent secret invalid")


def _is_admin(user: User) -> bool:
    role = (getattr(user, "role", "") or "").strip().lower()
    return role == "admin"


def _device_matches_filter(attrs: Optional[dict], flt: Optional[dict]) -> bool:
    """设备 account_attrs 是否满足 device_filter。"""
    if not flt:
        return True
    attrs = attrs or {}
    niche = (flt.get("niche") or "").strip()
    if niche and (attrs.get("niche") or "").strip() != niche:
        return False
    min_phase = (flt.get("min_phase") or "").strip()
    if min_phase:
        phase_order = {"nurture_phase_1": 1, "phase_2": 2, "post_ready": 3}
        dev_phase = (attrs.get("phase") or "").strip()
        if phase_order.get(dev_phase, 0) < phase_order.get(min_phase, 0):
            return False
    min_karma = flt.get("min_karma")
    if min_karma is not None and int(attrs.get("karma") or 0) < int(min_karma):
        return False
    tags = flt.get("tags")
    if tags and isinstance(tags, list):
        dev_tags = set(attrs.get("tags") or [])
        if not dev_tags.intersection(set(str(t) for t in tags)):
            return False
    return True


def _device_label_from_row(device: Optional[MobileDevice]) -> Optional[str]:
    if not device:
        return None
    meta = device.meta if isinstance(device.meta, dict) else {}
    label = str(meta.get("device_label") or meta.get("display_name") or "").strip()
    if label:
        return label
    alias = (device.alias or "").strip()
    if alias:
        return alias
    serial = (device.serial or "").strip()
    return serial or None


def _device_no_from_row(device: Optional[MobileDevice]) -> Optional[int]:
    if not device:
        return None
    meta = device.meta if isinstance(device.meta, dict) else {}
    raw = str(meta.get("device_no") or "").strip()
    if not raw:
        label = _device_label_from_row(device) or ""
        m = re.search(r"(\d+)$", label)
        raw = m.group(1) if m else ""
    if not raw:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _upsert_devices_for_agent(db: Session, agent: ControlAgent, devices: list[DeviceStateIn]) -> None:
    now = datetime.utcnow()
    for item in devices:
        serial = (item.serial or "").strip()
        if not serial:
            continue
        attrs = item.account_attrs
        if attrs is None and item.meta and isinstance(item.meta.get("account_attrs"), dict):
            attrs = item.meta["account_attrs"]
        row = db.query(MobileDevice).filter(MobileDevice.serial == serial).first()
        if not row:
            row = MobileDevice(
                serial=serial,
                alias=item.alias,
                platform=(item.platform or "android").strip() or "android",
                agent_id=agent.id,
                adb_status=(item.adb_status or "unknown")[:32],
                appium_status=(item.appium_status or "unknown")[:32],
                meta=item.meta,
                account_attrs=attrs,
                last_seen_at=now,
            )
            db.add(row)
            continue
        row.alias = item.alias
        row.platform = (item.platform or row.platform or "android").strip() or "android"
        row.agent_id = agent.id
        row.adb_status = (item.adb_status or "unknown")[:32]
        row.appium_status = (item.appium_status or "unknown")[:32]
        row.meta = item.meta
        if attrs is not None:
            row.account_attrs = attrs
        row.last_seen_at = now
        db.add(row)


@router.post("/agents/register", summary="执行节点注册（Agent）")
def register_agent(
    payload: AgentRegisterIn,
    db: Session = Depends(get_db),
    x_agent_secret: Optional[str] = Header(None, alias="X-Agent-Secret"),
):
    _ensure_agent_secret(x_agent_secret)
    key = payload.agent_key.strip()
    row = db.query(ControlAgent).filter(ControlAgent.agent_key == key).first()
    if not row:
        row = ControlAgent(
            name=payload.name.strip(),
            agent_key=key,
            host=(payload.host or "").strip() or None,
            labels=payload.labels,
            status="online",
            last_seen_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    else:
        row.name = payload.name.strip()
        row.host = (payload.host or "").strip() or None
        row.labels = payload.labels
        row.status = "online"
        row.last_seen_at = datetime.utcnow()
        db.add(row)
        db.commit()
        db.refresh(row)
    _upsert_devices_for_agent(db, row, payload.devices)
    db.commit()
    return {"agent_id": row.id, "agent_key": row.agent_key, "status": row.status}


@router.post("/agents/{agent_key}/heartbeat", summary="执行节点心跳（Agent）")
def heartbeat_agent(
    agent_key: str,
    payload: AgentHeartbeatIn,
    db: Session = Depends(get_db),
    x_agent_secret: Optional[str] = Header(None, alias="X-Agent-Secret"),
):
    _ensure_agent_secret(x_agent_secret)
    row = db.query(ControlAgent).filter(ControlAgent.agent_key == agent_key).first()
    if not row:
        raise HTTPException(status_code=404, detail="agent not found")
    row.host = (payload.host or row.host or "").strip() or None
    row.labels = payload.labels if payload.labels is not None else row.labels
    row.status = "online"
    row.last_seen_at = datetime.utcnow()
    db.add(row)
    _upsert_devices_for_agent(db, row, payload.devices)
    db.commit()
    return {"detail": "ok", "last_seen_at": row.last_seen_at.isoformat()}


class AgentDeviceAccountStateIn(BaseModel):
    serial: str
    username: Optional[str] = None
    status: Optional[str] = None  # active|warning|restricted|locked
    karma: Optional[int] = None
    risk_score: Optional[int] = None
    meta: Optional[dict[str, Any]] = None


@router.post("/agents/{agent_key}/device-account-state", summary="上报设备账号状态（Agent）")
def report_device_account_state(
    agent_key: str,
    payload: AgentDeviceAccountStateIn,
    db: Session = Depends(get_db),
    x_agent_secret: Optional[str] = Header(None, alias="X-Agent-Secret"),
):
    _ensure_agent_secret(x_agent_secret)
    agent = db.query(ControlAgent).filter(ControlAgent.agent_key == agent_key).first()
    if not agent:
        raise HTTPException(status_code=404, detail="agent not found")
    serial = (payload.serial or "").strip()
    if not serial:
        raise HTTPException(status_code=400, detail="serial required")
    dev = db.query(MobileDevice).filter(MobileDevice.serial == serial).first()
    if not dev:
        raise HTTPException(status_code=404, detail="device not found")
    meta = dev.meta if isinstance(dev.meta, dict) else {}
    account_state = {
        "username": (payload.username or "").strip() or None,
        "status": (payload.status or "").strip() or None,
        "karma": payload.karma,
        "risk_score": payload.risk_score,
        "reported_at": datetime.utcnow().isoformat(),
    }
    if payload.meta and isinstance(payload.meta, dict):
        account_state["meta"] = payload.meta
    meta["account_state"] = account_state
    dev.meta = meta
    attrs = dev.account_attrs if isinstance(dev.account_attrs, dict) else {}
    if payload.username:
        attrs["reddit_username"] = payload.username.strip()
    if payload.karma is not None:
        attrs["karma"] = int(payload.karma)
    if payload.status:
        attrs["account_health"] = payload.status.strip()
    if payload.risk_score is not None:
        attrs["risk_score"] = int(payload.risk_score)
    dev.account_attrs = attrs
    db.add(dev)

    # 已存在绑定则直接同步绑定状态，供云端策略实时使用。
    binding = (
        db.query(NurtureBinding)
        .filter(NurtureBinding.device_id == dev.id)
        .order_by(NurtureBinding.id.desc())
        .first()
    )
    if binding:
        if payload.karma is not None:
            binding.current_karma = max(0, int(payload.karma))
            if binding.current_karma >= int(binding.target_karma or 0):
                binding.eligible_for_posting = True
        if payload.status:
            binding.account_health = payload.status.strip()
        if payload.risk_score is not None:
            binding.risk_score = max(0, min(100, int(payload.risk_score)))
        db.add(binding)

    db.commit()
    return {"detail": "ok", "device_id": dev.id, "binding_id": binding.id if binding else None}


@router.get("/devices", summary="设备列表（用户态）")
def list_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if _is_admin(current_user):
        rows = db.query(MobileDevice).order_by(MobileDevice.updated_at.desc()).all()
    else:
        assigned_device_ids = [
            x.device_id
            for x in db.query(UserDeviceAssignment).filter(UserDeviceAssignment.user_id == current_user.id).all()
        ]
        if not assigned_device_ids:
            rows = []
        else:
            rows = (
                db.query(MobileDevice)
                .filter(MobileDevice.id.in_(assigned_device_ids))
                .order_by(MobileDevice.updated_at.desc())
                .all()
            )
    rows = sorted(
        rows,
        key=lambda r: (
            _device_no_from_row(r) is None,
            _device_no_from_row(r) if _device_no_from_row(r) is not None else 10**9,
            -int((r.updated_at or datetime.min).timestamp()),
        ),
    )
    return [
        {
            "id": r.id,
            "serial": None,
            "alias": r.alias,
            "device_label": _device_label_from_row(r),
            "device_no": _device_no_from_row(r),
            "platform": r.platform,
            "agent_id": r.agent_id,
            "adb_status": r.adb_status,
            "appium_status": r.appium_status,
            "meta": r.meta,
            "account_attrs": r.account_attrs if hasattr(r, "account_attrs") else None,
            "model": (r.meta or {}).get("model") if isinstance(r.meta, dict) else None,
            "brand": (r.meta or {}).get("brand") if isinstance(r.meta, dict) else None,
            "device_uid": (r.meta or {}).get("device_uid") if isinstance(r.meta, dict) else None,
            "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        }
        for r in rows
    ]


class DevicePatchIn(BaseModel):
    alias: Optional[str] = None
    account_attrs: Optional[dict[str, Any]] = None


@router.patch("/devices/{device_id}", summary="更新设备（用户态）")
def patch_device(
    device_id: int,
    payload: DevicePatchIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    row = db.query(MobileDevice).filter(MobileDevice.id == device_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="device not found")
    if payload.alias is not None:
        row.alias = payload.alias.strip() if payload.alias else None
    if payload.account_attrs is not None:
        row.account_attrs = payload.account_attrs
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "alias": row.alias, "account_attrs": getattr(row, "account_attrs", None)}


class RedditAccountIn(BaseModel):
    username: str = Field(..., min_length=2, max_length=128)
    password: Optional[str] = Field(default=None, max_length=255)
    source: str = Field(default="user", max_length=32)  # user|system
    status: str = Field(default="active", max_length=32)  # active|paused|disabled
    tags: Optional[list[str]] = None
    account_attrs: Optional[dict[str, Any]] = None


@router.get("/reddit-accounts", summary="Reddit账号资产列表（用户态）")
def list_reddit_accounts(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if _is_admin(current_user):
        q = db.query(RedditAccountAsset)
    else:
        assigned_ids = [
            x.reddit_account_id
            for x in db.query(UserRedditAccountAssignment)
            .filter(UserRedditAccountAssignment.user_id == current_user.id)
            .all()
        ]
        q = db.query(RedditAccountAsset).filter(
            or_(
                RedditAccountAsset.user_id == current_user.id,  # 用户自有账号
                RedditAccountAsset.id.in_(assigned_ids) if assigned_ids else RedditAccountAsset.id == -1,  # 系统分配账号
            )
        )
    if status_filter:
        q = q.filter(RedditAccountAsset.status == status_filter.strip())
    rows = q.order_by(RedditAccountAsset.updated_at.desc()).all()
    return [
        {
            "id": r.id,
            "username": r.username,
            "source": r.source,
            "status": r.status,
            "tags": r.tags,
            "account_attrs": r.account_attrs,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        }
        for r in rows
    ]


@router.post("/reddit-accounts", summary="创建Reddit账号资产（用户态）")
def create_reddit_account(
    payload: RedditAccountIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = (payload.source or "user").strip() or "user"
    if source == "system" and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="only admin can create system accounts")
    row = RedditAccountAsset(
        user_id=current_user.id,
        username=payload.username.strip(),
        password=payload.password,
        source=source,
        status=(payload.status or "active").strip() or "active",
        tags=payload.tags,
        account_attrs=payload.account_attrs,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "username": row.username, "status": row.status}


class DispatchGroupIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    device_ids: Optional[list[int]] = None
    account_ids: Optional[list[int]] = None
    notes: Optional[str] = Field(default=None, max_length=512)


@router.get("/dispatch-groups", summary="分组列表（用户态）")
def list_dispatch_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(ControlDispatchGroup)
        .filter(ControlDispatchGroup.user_id == current_user.id)
        .order_by(ControlDispatchGroup.updated_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "name": r.name,
            "device_ids": r.device_ids or [],
            "account_ids": r.account_ids or [],
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        }
        for r in rows
    ]


@router.post("/dispatch-groups", summary="创建分组（用户态）")
def create_dispatch_group(
    payload: DispatchGroupIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = ControlDispatchGroup(
        user_id=current_user.id,
        name=payload.name.strip(),
        device_ids=payload.device_ids or [],
        account_ids=payload.account_ids or [],
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name}


@router.patch("/dispatch-groups/{group_id}", summary="更新分组（用户态）")
def patch_dispatch_group(
    group_id: int,
    payload: DispatchGroupIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(ControlDispatchGroup)
        .filter(ControlDispatchGroup.id == group_id, ControlDispatchGroup.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="dispatch group not found")
    row.name = payload.name.strip()
    row.device_ids = payload.device_ids or []
    row.account_ids = payload.account_ids or []
    row.notes = payload.notes
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name}


@router.delete("/dispatch-groups/{group_id}", summary="删除分组（用户态）")
def delete_dispatch_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(ControlDispatchGroup)
        .filter(ControlDispatchGroup.id == group_id, ControlDispatchGroup.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="dispatch group not found")
    db.delete(row)
    db.commit()
    return {"detail": "deleted"}


class AssignDevicesIn(BaseModel):
    user_id: int
    device_ids: list[int] = Field(default_factory=list)


class AssignAccountsIn(BaseModel):
    user_id: int
    account_ids: list[int] = Field(default_factory=list)


def _allowed_device_ids_for_user(db: Session, current_user: User) -> set[int]:
    if _is_admin(current_user):
        rows = db.query(MobileDevice.id).all()
        return {r[0] for r in rows}
    return {
        x.device_id
        for x in db.query(UserDeviceAssignment).filter(UserDeviceAssignment.user_id == current_user.id).all()
    }


def _allowed_account_ids_for_user(db: Session, current_user: User) -> set[int]:
    if _is_admin(current_user):
        rows = db.query(RedditAccountAsset.id).all()
        return {r[0] for r in rows}
    own_ids = {x.id for x in db.query(RedditAccountAsset).filter(RedditAccountAsset.user_id == current_user.id).all()}
    assigned_system_ids = {
        x.reddit_account_id
        for x in db.query(UserRedditAccountAssignment)
        .filter(UserRedditAccountAssignment.user_id == current_user.id)
        .all()
    }
    return own_ids | assigned_system_ids


def _resolve_device_account_id(db: Session, current_user: User, device_id: int, explicit_account_id: Optional[int]) -> int:
    if explicit_account_id is not None:
        return int(explicit_account_id)
    dev = db.query(MobileDevice).filter(MobileDevice.id == device_id).first()
    meta = dev.meta if dev and isinstance(dev.meta, dict) else {}
    attrs = dev.account_attrs if dev and isinstance(dev.account_attrs, dict) else {}
    account_state = meta.get("account_state") if isinstance(meta.get("account_state"), dict) else {}
    username = str(
        account_state.get("username")
        or attrs.get("reddit_username")
        or attrs.get("username")
        or ""
    ).strip()
    if not username:
        label = _device_label_from_row(dev) or f"device-{device_id}"
        username = f"{label}-auto"
    row = (
        db.query(RedditAccountAsset)
        .filter(RedditAccountAsset.user_id == current_user.id, RedditAccountAsset.username == username)
        .first()
    )
    if not row:
        row = RedditAccountAsset(
            user_id=current_user.id,
            username=username,
            source="system" if _is_admin(current_user) else "user",
            status="active",
            account_attrs={"auto_discovered": True, "device_id": device_id},
        )
        db.add(row)
        db.flush()
    return int(row.id)


def _server_target_karma(db: Session, device_id: int, account_id: int) -> int:
    dev = db.query(MobileDevice).filter(MobileDevice.id == device_id).first()
    acc = db.query(RedditAccountAsset).filter(RedditAccountAsset.id == account_id).first()
    attrs = dev.account_attrs if dev and isinstance(dev.account_attrs, dict) else {}
    a_attrs = acc.account_attrs if acc and isinstance(acc.account_attrs, dict) else {}
    current_karma = int(a_attrs.get("karma") or attrs.get("karma") or 0)
    health = str(a_attrs.get("account_health") or attrs.get("account_health") or "healthy").strip().lower()
    if health in {"restricted", "warning"}:
        return 20
    if current_karma >= 20:
        return 40
    return 30


class NurtureBindingUpsertIn(BaseModel):
    device_id: int
    reddit_account_id: Optional[int] = None
    target_karma: Optional[int] = Field(default=None, ge=1, le=100000)
    phase: Optional[str] = None
    automation_mode: Optional[str] = None


class NurturePlanGenerateIn(BaseModel):
    binding_id: int
    objective: str = Field(default="safe_growth", max_length=64)  # safe_growth|balanced|fast_growth
    risk_preference: str = Field(default="conservative", max_length=32)  # conservative|balanced|aggressive
    start_date: Optional[str] = None  # YYYY-MM-DD, UTC
    name: Optional[str] = Field(default=None, max_length=128)


class NurturePlanGenerateByDeviceIn(BaseModel):
    device_id: int
    objective: str = Field(default="safe_growth", max_length=64)
    risk_preference: str = Field(default="conservative", max_length=32)
    start_date: Optional[str] = None
    name: Optional[str] = Field(default=None, max_length=128)
    auto_approve: bool = False


@router.get("/nurture/bindings", summary="养号绑定列表（用户态）")
def list_nurture_bindings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(NurtureBinding).filter(NurtureBinding.user_id == current_user.id)
    rows = q.order_by(NurtureBinding.updated_at.desc()).all()
    device_ids = sorted({r.device_id for r in rows})
    account_ids = sorted({r.reddit_account_id for r in rows})
    device_map: dict[int, MobileDevice] = {}
    account_map: dict[int, RedditAccountAsset] = {}
    if device_ids:
        for d in db.query(MobileDevice).filter(MobileDevice.id.in_(device_ids)).all():
            device_map[d.id] = d
    if account_ids:
        for a in db.query(RedditAccountAsset).filter(RedditAccountAsset.id.in_(account_ids)).all():
            account_map[a.id] = a
    return [
        {
            "id": r.id,
            "device_id": r.device_id,
            "device_label": _device_label_from_row(device_map.get(r.device_id)),
            "reddit_account_id": r.reddit_account_id,
            "reddit_username": (account_map.get(r.reddit_account_id).username if account_map.get(r.reddit_account_id) else None),
            "status": r.status,
            "phase": r.phase,
            "account_health": r.account_health,
            "automation_mode": r.automation_mode,
            "risk_score": r.risk_score,
            "target_karma": r.target_karma,
            "current_karma": r.current_karma,
            "eligible_for_posting": bool(r.eligible_for_posting),
            "last_incident_code": r.last_incident_code,
            "last_incident_at": _iso(r.last_incident_at),
            "next_action_at": _iso(r.next_action_at),
            "updated_at": _iso(r.updated_at),
        }
        for r in rows
    ]


@router.post("/nurture/bindings", summary="创建或更新养号绑定（用户态）")
def upsert_nurture_binding(
    payload: NurtureBindingUpsertIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed_devices = _allowed_device_ids_for_user(db, current_user)
    if payload.device_id not in allowed_devices:
        raise HTTPException(status_code=403, detail="device not allowed")
    resolved_account_id = _resolve_device_account_id(db, current_user, payload.device_id, payload.reddit_account_id)
    resolved_target_karma = int(payload.target_karma) if payload.target_karma is not None else _server_target_karma(db, payload.device_id, resolved_account_id)
    allowed_accounts = _allowed_account_ids_for_user(db, current_user)
    if resolved_account_id not in allowed_accounts and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="reddit account not allowed")
    row = (
        db.query(NurtureBinding)
        .filter(
            NurtureBinding.user_id == current_user.id,
            NurtureBinding.device_id == payload.device_id,
        )
        .order_by(NurtureBinding.id.desc())
        .first()
    )
    if not row:
        row = NurtureBinding(
            user_id=current_user.id,
            device_id=payload.device_id,
            reddit_account_id=resolved_account_id,
            target_karma=resolved_target_karma,
            phase=(payload.phase or "warmup").strip() or "warmup",
            automation_mode=(payload.automation_mode or "normal").strip() or "normal",
            status="active",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"id": row.id, "detail": "created"}
    row.reddit_account_id = resolved_account_id
    row.target_karma = resolved_target_karma
    if payload.phase is not None:
        row.phase = (payload.phase or "").strip() or row.phase
    if payload.automation_mode is not None:
        row.automation_mode = (payload.automation_mode or "").strip() or row.automation_mode
    row.status = "active"
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "detail": "updated"}


@router.post("/nurture/plans/generate", summary="生成养号计划草案（用户态，云端 OpenClaw）")
def generate_nurture_plan(
    payload: NurturePlanGenerateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _generate_nurture_plan_for_binding(
        db=db,
        current_user=current_user,
        binding_id=payload.binding_id,
        objective=(payload.objective or "safe_growth").strip() or "safe_growth",
        risk_preference=(payload.risk_preference or "conservative").strip() or "conservative",
        start_date=payload.start_date,
        name=payload.name,
    )


def _generate_nurture_plan_for_binding(
    db: Session,
    current_user: User,
    binding_id: int,
    objective: str,
    risk_preference: str,
    start_date: Optional[str],
    name: Optional[str],
) -> dict[str, Any]:
    binding = (
        db.query(NurtureBinding)
        .filter(NurtureBinding.id == binding_id, NurtureBinding.user_id == current_user.id)
        .first()
    )
    if not binding:
        raise HTTPException(status_code=404, detail="binding not found")
    plan_json = _call_openclaw_for_plan(
        current_user,
        binding,
        objective=objective,
        risk_preference=risk_preference,
    )
    if not isinstance(plan_json, dict):
        plan_json = _build_fallback_plan(30)
    days = int(plan_json.get("plan_horizon_days") or 30)
    if days < 1:
        days = 30
    if days > 180:
        days = 180
    schedule = plan_json.get("schedule") if isinstance(plan_json, dict) else None
    if not isinstance(schedule, list) or not schedule:
        raise HTTPException(status_code=400, detail="invalid plan schedule")
    plan_name = (name or f"nurture-plan-binding-{binding.id}").strip() or f"nurture-plan-binding-{binding.id}"
    row = NurturePlan(
        user_id=current_user.id,
        binding_id=binding.id,
        name=plan_name,
        status="draft",
        plan_version=str(plan_json.get("plan_version") or "v1"),
        approval_mode="plan_once_then_auto",
        plan_horizon_days=days,
        requires_reconfirm=False,
        summary=str(plan_json.get("summary") or ""),
        last_review_at=datetime.utcnow(),
        next_review_at=datetime.utcnow() + timedelta(days=max(1, min(3, int(plan_json.get("next_review_in_days") or 1)))),
        plan_json=plan_json,
    )
    db.add(row)
    db.flush()
    # 先清理该计划残留条目（理论首次无残留）
    db.query(NurtureScheduleItem).filter(NurtureScheduleItem.plan_id == row.id).delete()
    start_dt = None
    if start_date:
        try:
            start_dt = datetime.strptime(start_date.strip(), "%Y-%m-%d")
        except Exception:
            raise HTTPException(status_code=400, detail="start_date format must be YYYY-MM-DD")
    if not start_dt:
        now = datetime.utcnow()
        start_dt = datetime(now.year, now.month, now.day)
    created = 0
    for item in schedule:
        if not isinstance(item, dict):
            continue
        day_no = int(item.get("day_no") or 1)
        seq_no = int(item.get("seq_no") or 1)
        hour = int(item.get("hour") or 10)
        minute = int(item.get("minute") or 0)
        when = start_dt + timedelta(days=max(day_no - 1, 0), hours=hour, minutes=minute)
        db.add(
            NurtureScheduleItem(
                user_id=current_user.id,
                binding_id=binding.id,
                plan_id=row.id,
                day_no=day_no,
                seq_no=seq_no,
                stage=str(item.get("stage") or binding.phase or "warmup"),
                title=str(item.get("title") or f"nurture-day{day_no:02d}-s{seq_no}"),
                scheduled_at=when,
                status="scheduled",
                payload=item.get("payload") if isinstance(item.get("payload"), dict) else {},
            )
        )
        created += 1
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "binding_id": row.binding_id,
        "status": row.status,
        "approval_mode": row.approval_mode,
        "plan_horizon_days": row.plan_horizon_days,
        "summary": row.summary,
        "created_schedule_count": created,
    }


@router.post("/nurture/plans/generate-by-device", summary="按设备直接创建养号计划（用户态）")
def generate_nurture_plan_by_device(
    payload: NurturePlanGenerateByDeviceIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bind_ret = upsert_nurture_binding(
        NurtureBindingUpsertIn(
            device_id=payload.device_id,
            reddit_account_id=None,
            target_karma=None,
            phase=None,
            automation_mode=None,
        ),
        db=db,
        current_user=current_user,
    )
    binding_id = int(bind_ret.get("id") or 0)
    if not binding_id:
        raise HTTPException(status_code=500, detail="failed to ensure binding")
    result = _generate_nurture_plan_for_binding(
        db=db,
        current_user=current_user,
        binding_id=binding_id,
        objective=(payload.objective or "safe_growth").strip() or "safe_growth",
        risk_preference=(payload.risk_preference or "conservative").strip() or "conservative",
        start_date=payload.start_date,
        name=payload.name,
    )
    if payload.auto_approve and result.get("id"):
        _ = approve_nurture_plan(plan_id=int(result["id"]), db=db, current_user=current_user)
        result["status"] = "approved"
        result["auto_approved"] = True
    else:
        result["auto_approved"] = False
    return result


@router.post("/nurture/plans/generate-batch", summary="批量为所有设备创建养号计划（用户态）")
def generate_nurture_plans_batch(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device_ids = sorted(_allowed_device_ids_for_user(db, current_user))
    if not device_ids:
        return {"detail": "no devices", "results": []}
    results: list[dict[str, Any]] = []
    for did in device_ids:
        try:
            r = generate_nurture_plan_by_device(
                payload=NurturePlanGenerateByDeviceIn(device_id=did, auto_approve=False),
                db=db,
                current_user=current_user,
            )
            results.append({"device_id": did, "ok": True, "plan_id": r.get("id"), "binding_id": r.get("binding_id")})
        except HTTPException as e:
            results.append({"device_id": did, "ok": False, "error": e.detail})
        except Exception as e:
            results.append({"device_id": did, "ok": False, "error": str(e)[:200]})
    ok_count = sum(1 for x in results if x["ok"])
    return {"detail": f"batch done: {ok_count}/{len(results)} succeeded", "results": results}


@router.get("/nurture/plans", summary="养号计划列表（用户态）")
def list_nurture_plans(
    binding_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(NurturePlan).filter(NurturePlan.user_id == current_user.id)
    if binding_id:
        q = q.filter(NurturePlan.binding_id == binding_id)
    rows = q.order_by(NurturePlan.updated_at.desc()).limit(200).all()
    return [
        {
            "id": r.id,
            "binding_id": r.binding_id,
            "name": r.name,
            "status": r.status,
            "plan_version": r.plan_version,
            "approval_mode": r.approval_mode,
            "plan_horizon_days": getattr(r, "plan_horizon_days", 30),
            "requires_reconfirm": bool(getattr(r, "requires_reconfirm", False)),
            "summary": r.summary,
            "approved_by": r.approved_by,
            "approved_at": _iso(r.approved_at),
            "start_at": _iso(r.start_at),
            "last_review_at": _iso(getattr(r, "last_review_at", None)),
            "next_review_at": _iso(getattr(r, "next_review_at", None)),
            "created_at": _iso(r.created_at),
            "updated_at": _iso(r.updated_at),
        }
        for r in rows
    ]


@router.post("/nurture/plans/{plan_id}/approve", summary="确认计划并开始自动执行（用户态）")
def approve_nurture_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(NurturePlan).filter(NurturePlan.id == plan_id, NurturePlan.user_id == current_user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="plan not found")
    row.status = "approved"
    row.requires_reconfirm = False
    row.approved_by = current_user.id
    row.approved_at = datetime.utcnow()
    row.last_review_at = datetime.utcnow()
    row.next_review_at = datetime.utcnow() + timedelta(days=1)
    db.add(row)
    db.commit()
    dispatched = _dispatch_due_nurture_items(db)
    return {"detail": "approved", "plan_id": row.id, "dispatched_now": dispatched}


@router.post("/nurture/plans/{plan_id}/pause", summary="暂停计划（用户态）")
def pause_nurture_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(NurturePlan).filter(NurturePlan.id == plan_id, NurturePlan.user_id == current_user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="plan not found")
    row.status = "paused"
    db.add(row)
    db.commit()
    return {"detail": "paused", "plan_id": row.id}


@router.delete("/nurture/plans/{plan_id}", summary="删除计划及其执行明细（用户态）")
def delete_nurture_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(NurturePlan).filter(NurturePlan.id == plan_id, NurturePlan.user_id == current_user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="plan not found")
    schedule_items = db.query(NurtureScheduleItem).filter(NurtureScheduleItem.plan_id == plan_id).all()
    linked_task_ids = [s.task_id for s in schedule_items if s.task_id]
    db.query(NurtureScheduleItem).filter(NurtureScheduleItem.plan_id == plan_id).delete(synchronize_session=False)
    if linked_task_ids:
        exec_ids = [e.id for e in db.query(TaskExecution).filter(TaskExecution.task_id.in_(linked_task_ids)).all()]
        if exec_ids:
            db.query(TaskExecutionLog).filter(TaskExecutionLog.execution_id.in_(exec_ids)).delete(synchronize_session=False)
            db.query(TaskExecution).filter(TaskExecution.id.in_(exec_ids)).delete(synchronize_session=False)
        db.query(ControlTask).filter(ControlTask.id.in_(linked_task_ids)).delete(synchronize_session=False)
    db.delete(row)
    db.commit()
    return {"detail": "deleted", "plan_id": plan_id}


@router.post("/nurture/scheduler/tick", summary="触发一次到点任务派发（用户态）")
def tick_nurture_scheduler(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    dispatched = _dispatch_due_nurture_items(db)
    return {"detail": "ok", "dispatched": dispatched}


@router.get("/nurture/strategy/latest", summary="每日策略复审结果（用户态）")
def get_latest_nurture_strategy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    snap = _daily_strategy_scan_if_due(db)
    if not snap:
        return {"snapshot": None}
    return {
        "snapshot": {
            "id": snap.id,
            "reviewed_date": snap.reviewed_date.isoformat() if isinstance(snap.reviewed_date, date) else str(snap.reviewed_date),
            "source": snap.source,
            "severity": snap.severity,
            "summary": snap.summary,
            "recommendations": snap.recommendations,
            "requires_reconfirm": bool(snap.requires_reconfirm),
            "created_at": _iso(snap.created_at),
        }
    }


@router.get("/nurture/schedule", summary="计划执行明细（用户态）")
def list_nurture_schedule(
    binding_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _dispatch_due_nurture_items(db)
    q = db.query(NurtureScheduleItem).filter(NurtureScheduleItem.user_id == current_user.id)
    if binding_id:
        q = q.filter(NurtureScheduleItem.binding_id == binding_id)
    if status_filter:
        q = q.filter(NurtureScheduleItem.status == status_filter.strip())
    rows = (
        q.order_by(
            NurtureScheduleItem.day_no.asc(),
            NurtureScheduleItem.seq_no.asc(),
            NurtureScheduleItem.scheduled_at.asc(),
            NurtureScheduleItem.id.asc(),
        )
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 500))
        .all()
    )
    task_ids = sorted({x.control_task_id for x in rows if x.control_task_id})
    task_map: dict[int, ControlTask] = {}
    if task_ids:
        for t in db.query(ControlTask).filter(ControlTask.id.in_(task_ids)).all():
            task_map[t.id] = t
    execution_map: dict[int, TaskExecution] = {}
    if task_ids:
        exes = (
            db.query(TaskExecution)
            .filter(TaskExecution.task_id.in_(task_ids))
            .order_by(TaskExecution.id.desc())
            .all()
        )
        for e in exes:
            if e.task_id not in execution_map:
                execution_map[e.task_id] = e
    return [
        {
            "id": r.id,
            "plan_id": r.plan_id,
            "binding_id": r.binding_id,
            "day_no": r.day_no,
            "seq_no": r.seq_no,
            "stage": r.stage,
            "title": r.title,
            "scheduled_at": _iso(r.scheduled_at),
            "status": r.status,
            "payload": r.payload,
            "control_task_id": r.control_task_id,
            "task_status": task_map[r.control_task_id].status if r.control_task_id and task_map.get(r.control_task_id) else None,
            "task_started_at": _iso(task_map[r.control_task_id].started_at) if r.control_task_id and task_map.get(r.control_task_id) else None,
            "task_finished_at": _iso(task_map[r.control_task_id].finished_at) if r.control_task_id and task_map.get(r.control_task_id) else None,
            "execution_status": execution_map[r.control_task_id].status if r.control_task_id and execution_map.get(r.control_task_id) else None,
            "execution_error_code": execution_map[r.control_task_id].error_code if r.control_task_id and execution_map.get(r.control_task_id) else None,
            "last_error_code": r.last_error_code,
            "last_error_message": r.last_error_message,
            "dispatched_at": _iso(r.dispatched_at),
            "started_at": _iso(r.started_at),
            "finished_at": _iso(r.finished_at),
        }
        for r in rows
    ]


@router.get("/nurture/progress", summary="养号进度看板（用户态）")
def nurture_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bindings = (
        db.query(NurtureBinding)
        .filter(NurtureBinding.user_id == current_user.id)
        .order_by(NurtureBinding.created_at.desc())
        .all()
    )
    if not bindings:
        return []
    device_ids = sorted({b.device_id for b in bindings})
    account_ids = sorted({b.reddit_account_id for b in bindings})
    binding_ids = sorted({b.id for b in bindings})
    d_map: dict[int, MobileDevice] = {}
    a_map: dict[int, RedditAccountAsset] = {}
    for d in db.query(MobileDevice).filter(MobileDevice.id.in_(device_ids)).all():
        d_map[d.id] = d
    for a in db.query(RedditAccountAsset).filter(RedditAccountAsset.id.in_(account_ids)).all():
        a_map[a.id] = a
    latest_plan_map: dict[int, NurturePlan] = {}
    plans = (
        db.query(NurturePlan)
        .filter(NurturePlan.binding_id.in_(binding_ids))
        .order_by(NurturePlan.id.desc())
        .all()
    )
    for p in plans:
        if p.binding_id not in latest_plan_map:
            latest_plan_map[p.binding_id] = p
    plan_ids = [p.id for p in latest_plan_map.values()]
    agg: dict[int, dict[str, int]] = {pid: {"total": 0, "success": 0, "failed": 0, "running": 0, "scheduled": 0} for pid in plan_ids}
    if plan_ids:
        for s in db.query(NurtureScheduleItem).filter(NurtureScheduleItem.plan_id.in_(plan_ids)).all():
            x = agg.setdefault(s.plan_id, {"total": 0, "success": 0, "failed": 0, "running": 0, "scheduled": 0})
            x["total"] += 1
            if s.status == "success":
                x["success"] += 1
            elif s.status == "failed":
                x["failed"] += 1
            elif s.status in {"running", "dispatched"}:
                x["running"] += 1
            else:
                x["scheduled"] += 1
    out: list[dict[str, Any]] = []
    for b in bindings:
        p = latest_plan_map.get(b.id)
        stat = agg.get(p.id, {"total": 0, "success": 0, "failed": 0, "running": 0, "scheduled": 0}) if p else {"total": 0, "success": 0, "failed": 0, "running": 0, "scheduled": 0}
        out.append(
            {
                "binding_id": b.id,
                "device_id": b.device_id,
                "device_label": _device_label_from_row(d_map.get(b.device_id)),
                "reddit_account_id": b.reddit_account_id,
                "reddit_username": (a_map.get(b.reddit_account_id).username if a_map.get(b.reddit_account_id) else None),
                "phase": b.phase,
                "status": b.status,
                "account_health": b.account_health,
                "automation_mode": b.automation_mode,
                "risk_score": b.risk_score,
                "current_karma": b.current_karma,
                "target_karma": b.target_karma,
                "eligible_for_posting": bool(b.eligible_for_posting),
                "plan_id": p.id if p else None,
                "plan_status": p.status if p else None,
                "plan_horizon_days": (getattr(p, "plan_horizon_days", None) if p else None),
                "plan_requires_reconfirm": (bool(getattr(p, "requires_reconfirm", False)) if p else False),
                "plan_updated_at": _iso(p.updated_at) if p else None,
                "metrics": stat,
                "next_action_at": _iso(b.next_action_at),
                "created_at": _iso(b.created_at),
                "updated_at": _iso(b.updated_at),
            }
        )
    return out


@router.get("/admin/users", summary="管理员查看用户列表")
def list_users_for_admin(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="admin only")
    rows = db.query(User).order_by(User.id.asc()).all()
    return [{"id": u.id, "email": u.email, "role": getattr(u, "role", "user")} for u in rows]


@router.get("/admin/user-assignments/{user_id}", summary="管理员查看用户资源分配")
def get_user_assignments_for_admin(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="admin only")
    device_ids = [
        x.device_id
        for x in db.query(UserDeviceAssignment).filter(UserDeviceAssignment.user_id == user_id).all()
    ]
    account_ids = [
        x.reddit_account_id
        for x in db.query(UserRedditAccountAssignment).filter(UserRedditAccountAssignment.user_id == user_id).all()
    ]
    return {"user_id": user_id, "device_ids": device_ids, "account_ids": account_ids}


@router.post("/admin/assign-devices", summary="管理员分配设备")
def assign_devices_to_user(
    payload: AssignDevicesIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="admin only")
    # 全量替换分配
    db.query(UserDeviceAssignment).filter(UserDeviceAssignment.user_id == payload.user_id).delete()
    for did in payload.device_ids:
        db.add(
            UserDeviceAssignment(
                user_id=payload.user_id,
                device_id=did,
                assigned_by=current_user.id,
            )
        )
    db.commit()
    return {"detail": "ok", "assigned_count": len(payload.device_ids)}


@router.post("/admin/assign-reddit-accounts", summary="管理员分配系统账号")
def assign_accounts_to_user(
    payload: AssignAccountsIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="admin only")
    db.query(UserRedditAccountAssignment).filter(UserRedditAccountAssignment.user_id == payload.user_id).delete()
    for aid in payload.account_ids:
        db.add(
            UserRedditAccountAssignment(
                user_id=payload.user_id,
                reddit_account_id=aid,
                assigned_by=current_user.id,
            )
        )
    db.commit()
    return {"detail": "ok", "assigned_count": len(payload.account_ids)}


@router.post("/tasks", summary="创建群控任务（用户态）")
def create_task(
    payload: CreateTaskIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device_ids = list(payload.target_device_ids or [])
    account_ids = list(payload.target_account_ids or [])
    if payload.target_device_id is not None:
        device_ids.append(payload.target_device_id)
    if payload.target_account_id is not None:
        account_ids.append(payload.target_account_id)
    # 去重并保序
    device_ids = list(dict.fromkeys([x for x in device_ids if isinstance(x, int)]))
    account_ids = list(dict.fromkeys([x for x in account_ids if isinstance(x, int)]))

    if payload.target_group_id is not None:
        grp = (
            db.query(ControlDispatchGroup)
            .filter(
                ControlDispatchGroup.id == payload.target_group_id,
                ControlDispatchGroup.user_id == current_user.id,
            )
            .first()
        )
        if not grp:
            raise HTTPException(status_code=404, detail="dispatch group not found")
        if not device_ids:
            device_ids = [int(x) for x in (grp.device_ids or []) if isinstance(x, int) or str(x).isdigit()]
        if not account_ids:
            account_ids = [int(x) for x in (grp.account_ids or []) if isinstance(x, int) or str(x).isdigit()]

    if not _is_admin(current_user):
        allowed_device_ids = {
            x.device_id
            for x in db.query(UserDeviceAssignment).filter(UserDeviceAssignment.user_id == current_user.id).all()
        }
        if device_ids and not set(device_ids).issubset(allowed_device_ids):
            raise HTTPException(status_code=403, detail="contains unassigned devices")
        allowed_account_ids = {x.id for x in db.query(RedditAccountAsset).filter(RedditAccountAsset.user_id == current_user.id).all()}
        assigned_system_account_ids = {
            x.reddit_account_id
            for x in db.query(UserRedditAccountAssignment)
            .filter(UserRedditAccountAssignment.user_id == current_user.id)
            .all()
        }
        allowed_account_ids |= assigned_system_account_ids
        if account_ids and not set(account_ids).issubset(allowed_account_ids):
            raise HTTPException(status_code=403, detail="contains unassigned accounts")

    task_rows: list[ControlTask] = []
    base_payload = dict(payload.payload or {})

    def _new_row(dev_id: Optional[int], acc_id: Optional[int]) -> ControlTask:
        task_payload = dict(base_payload)
        if acc_id is not None:
            task_payload["reddit_account_id"] = acc_id
        return ControlTask(
            user_id=current_user.id,
            title=payload.title.strip(),
            platform=(payload.platform or "reddit").strip() or "reddit",
            task_type=(payload.task_type or "reddit_flow").strip() or "reddit_flow",
            payload=task_payload,
            target_device_id=dev_id,
            target_account_id=acc_id,
            dispatch_group_id=payload.target_group_id,
            device_filter=payload.device_filter,
            priority=payload.priority,
            max_retries=payload.max_retries,
            status="pending",
        )

    if device_ids and account_ids:
        if len(account_ids) == 1:
            for dev_id in device_ids:
                task_rows.append(_new_row(dev_id, account_ids[0]))
        elif len(device_ids) == len(account_ids):
            for dev_id, acc_id in zip(device_ids, account_ids):
                task_rows.append(_new_row(dev_id, acc_id))
        else:
            # 默认降级为前 N 个一一对应，避免组合爆炸
            size = min(len(device_ids), len(account_ids))
            for i in range(size):
                task_rows.append(_new_row(device_ids[i], account_ids[i]))
    elif device_ids:
        for dev_id in device_ids:
            task_rows.append(_new_row(dev_id, None))
    elif account_ids:
        for acc_id in account_ids:
            task_rows.append(_new_row(None, acc_id))
    else:
        task_rows.append(_new_row(None, None))

    for row in task_rows:
        db.add(row)
    db.commit()
    for row in task_rows:
        db.refresh(row)
    return {
        "id": task_rows[0].id if task_rows else None,
        "status": "pending",
        "created_count": len(task_rows),
        "task_ids": [r.id for r in task_rows],
    }


@router.get("/tasks", summary="任务列表（用户态）")
def list_tasks(
    status_filter: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(ControlTask).filter(ControlTask.user_id == current_user.id)
    if status_filter:
        q = q.filter(ControlTask.status == status_filter.strip())
    rows = (
        q.order_by(ControlTask.created_at.desc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 500))
        .all()
    )
    assigned_ids = sorted({r.assigned_device_id for r in rows if r.assigned_device_id})
    device_map: dict[int, MobileDevice] = {}
    if assigned_ids:
        for d in db.query(MobileDevice).filter(MobileDevice.id.in_(assigned_ids)).all():
            device_map[d.id] = d
    return [
        {
            "id": r.id,
            "title": r.title,
            "platform": r.platform,
            "task_type": r.task_type,
            "status": r.status,
            "target_device_id": r.target_device_id,
            "target_account_id": getattr(r, "target_account_id", None),
            "dispatch_group_id": getattr(r, "dispatch_group_id", None),
            "nurture_schedule_item_id": getattr(r, "nurture_schedule_item_id", None),
            "device_filter": getattr(r, "device_filter", None),
            "assigned_agent_id": r.assigned_agent_id,
            "assigned_device_id": r.assigned_device_id,
            "assigned_device_label": _device_label_from_row(device_map.get(r.assigned_device_id or -1)),
            "priority": r.priority,
            "retries": r.retries,
            "max_retries": r.max_retries,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in rows
    ]


@router.get("/tasks/{task_id}", summary="任务详情（用户态）")
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(ControlTask).filter(ControlTask.id == task_id, ControlTask.user_id == current_user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="task not found")
    logs = (
        db.query(TaskExecutionLog, TaskExecution)
        .join(TaskExecution, TaskExecution.id == TaskExecutionLog.execution_id)
        .filter(TaskExecution.task_id == row.id)
        .order_by(TaskExecutionLog.created_at.desc())
        .limit(200)
        .all()
    )
    assigned_device = None
    if row.assigned_device_id:
        assigned_device = db.query(MobileDevice).filter(MobileDevice.id == row.assigned_device_id).first()
    return {
        "task": {
            "id": row.id,
            "title": row.title,
            "platform": row.platform,
            "task_type": row.task_type,
            "status": row.status,
            "payload": row.payload,
            "target_device_id": row.target_device_id,
            "target_account_id": getattr(row, "target_account_id", None),
            "dispatch_group_id": getattr(row, "dispatch_group_id", None),
            "nurture_schedule_item_id": getattr(row, "nurture_schedule_item_id", None),
            "device_filter": getattr(row, "device_filter", None),
            "assigned_agent_id": row.assigned_agent_id,
            "assigned_device_id": row.assigned_device_id,
            "assigned_device_label": _device_label_from_row(assigned_device),
            "retries": row.retries,
            "max_retries": row.max_retries,
            "created_at": row.created_at.isoformat() if row.created_at else "",
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        },
        "logs": [
            {
                "id": log.id,
                "execution_id": log.execution_id,
                "level": log.level,
                "message": log.message,
                "screenshot_url": log.screenshot_url,
                "payload": log.payload,
                "created_at": log.created_at.isoformat() if log.created_at else "",
                "execution_status": exe.status,
            }
            for log, exe in logs
        ],
    }


@router.post("/tasks/{task_id}/cancel", summary="取消任务（用户态）")
def cancel_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(ControlTask).filter(ControlTask.id == task_id, ControlTask.user_id == current_user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="task not found")
    if row.status in ("success", "failed", "cancelled"):
        return {"detail": "already finished", "status": row.status}
    row.status = "cancelled"
    row.finished_at = datetime.utcnow()
    db.add(row)
    db.commit()
    return {"detail": "cancelled", "status": row.status}


@router.delete("/tasks/{task_id}", summary="删除任务（用户态）")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(ControlTask).filter(ControlTask.id == task_id, ControlTask.user_id == current_user.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="task not found")
    exec_ids = [e.id for e in db.query(TaskExecution).filter(TaskExecution.task_id == task_id).all()]
    if exec_ids:
        db.query(TaskExecutionLog).filter(TaskExecutionLog.execution_id.in_(exec_ids)).delete(synchronize_session=False)
        db.query(TaskExecution).filter(TaskExecution.id.in_(exec_ids)).delete(synchronize_session=False)
    db.delete(row)
    db.commit()
    return {"detail": "deleted", "task_id": task_id}


@router.post("/agents/{agent_key}/next-task", summary="拉取待执行任务（Agent）")
def poll_next_task(
    agent_key: str,
    payload: AgentPollIn,
    db: Session = Depends(get_db),
    x_agent_secret: Optional[str] = Header(None, alias="X-Agent-Secret"),
):
    try:
        _ensure_agent_secret(x_agent_secret)
        _dispatch_due_nurture_items(db)
        agent = db.query(ControlAgent).filter(ControlAgent.agent_key == agent_key).first()
        if not agent:
            raise HTTPException(status_code=404, detail="agent not found")

        agent.status = "online"
        agent.last_seen_at = datetime.utcnow()
        db.add(agent)

        device_ids: list[int] = []
        serials = {x.strip() for x in payload.device_serials if x and x.strip()}
        if serials:
            rows = db.query(MobileDevice).filter(MobileDevice.serial.in_(serials)).all()
            for item in rows:
                item.agent_id = agent.id
                item.last_seen_at = datetime.utcnow()
                db.add(item)
                device_ids.append(item.id)

        now = datetime.utcnow()
        q = db.query(ControlTask).filter(
            ControlTask.status == "pending",
            or_(ControlTask.lease_until.is_(None), ControlTask.lease_until < now),
        )
        if device_ids:
            q = q.filter(or_(ControlTask.target_device_id.is_(None), ControlTask.target_device_id.in_(device_ids)))
        rows = q.order_by(ControlTask.priority.asc(), ControlTask.created_at.asc()).all()
        row = None
        matched_device_id: Optional[int] = None
        for r in rows:
            flt = getattr(r, "device_filter", None)
            if not flt:
                row = r
                break
            for did in device_ids:
                dev = db.query(MobileDevice).filter(MobileDevice.id == did).first()
                if dev and _device_matches_filter(getattr(dev, "account_attrs", None), flt):
                    if r.target_device_id is None or r.target_device_id == did:
                        row = r
                        matched_device_id = did
                        break
            if row:
                break
        if not row:
            db.commit()
            return {"task": None}

        row.status = "running"
        row.assigned_agent_id = agent.id
        if matched_device_id is not None:
            row.assigned_device_id = matched_device_id
        else:
            row.assigned_device_id = row.target_device_id if row.target_device_id in device_ids else (device_ids[0] if device_ids else row.target_device_id)
        row.lease_until = now + timedelta(seconds=max(settings.control_task_lease_seconds, 30))
        row.started_at = row.started_at or now
        db.add(row)

        execution = TaskExecution(
            task_id=row.id,
            user_id=row.user_id,
            agent_id=agent.id,
            device_id=row.assigned_device_id,
            status="running",
            started_at=now,
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        db.refresh(row)
        assigned_serial = None
        assigned_label = None
        if row.assigned_device_id:
            d = db.query(MobileDevice).filter(MobileDevice.id == row.assigned_device_id).first()
            assigned_serial = d.serial if d else None
            assigned_label = _device_label_from_row(d)

        return {
            "task": {
                "id": row.id,
                "platform": row.platform,
                "task_type": row.task_type,
                "title": row.title,
                "payload": row.payload,
                "assigned_device_id": row.assigned_device_id,
                "assigned_device_serial": assigned_serial,
                "assigned_device_label": assigned_label,
                "target_account_id": getattr(row, "target_account_id", None),
                "nurture_schedule_item_id": getattr(row, "nurture_schedule_item_id", None),
                "execution_id": execution.id,
                "lease_until": row.lease_until.isoformat() if row.lease_until else None,
            }
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "poll_next_task internal error",
            extra={
                "agent_key": agent_key,
                "serial_count": len(payload.device_serials or []),
            },
        )
        raise HTTPException(status_code=502, detail="poll_next_task_internal_error")


@router.post("/tasks/{task_id}/report", summary="上报执行进度或结果（Agent）")
def report_task(
    task_id: int,
    payload: TaskReportIn,
    db: Session = Depends(get_db),
    x_agent_secret: Optional[str] = Header(None, alias="X-Agent-Secret"),
):
    _ensure_agent_secret(x_agent_secret)
    row = db.query(ControlTask).filter(ControlTask.id == task_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="task not found")

    execution: Optional[TaskExecution] = None
    if payload.execution_id is not None:
        execution = db.query(TaskExecution).filter(TaskExecution.id == payload.execution_id, TaskExecution.task_id == row.id).first()
    if execution is None:
        execution = (
            db.query(TaskExecution)
            .filter(TaskExecution.task_id == row.id)
            .order_by(TaskExecution.id.desc())
            .first()
        )
    if execution is None:
        execution = TaskExecution(
            task_id=row.id,
            user_id=row.user_id,
            agent_id=row.assigned_agent_id,
            device_id=row.assigned_device_id,
            status="running",
            started_at=datetime.utcnow(),
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)

    execution.step = (payload.step or "")[:128] or None
    execution.error_code = (payload.error_code or "")[:64] or None
    execution.error_message = (payload.error_message or "")[:5000] or None
    execution.metrics = payload.metrics
    execution.status = payload.status
    if payload.status in ("success", "failed", "cancelled"):
        execution.finished_at = datetime.utcnow()

    for item in payload.logs:
        db.add(
            TaskExecutionLog(
                execution_id=execution.id,
                level=(item.level or "info")[:16],
                message=(item.message or "")[:5000],
                screenshot_url=(item.screenshot_url or "")[:512] or None,
                payload=item.payload,
            )
        )

    if payload.status in ("running",):
        row.status = "running"
        row.lease_until = datetime.utcnow() + timedelta(seconds=max(settings.control_task_lease_seconds, 30))
    elif payload.status in ("success", "failed", "cancelled"):
        row.status = payload.status
        row.finished_at = datetime.utcnow()
        row.lease_until = None
        if payload.status == "failed" and row.retries < row.max_retries:
            row.retries += 1
            row.status = "pending"
            row.assigned_agent_id = None
            row.assigned_device_id = None
            row.lease_until = None
            row.finished_at = None

    db.add(execution)
    db.add(row)

    # 同步养号计划执行状态与绑定进度
    if getattr(row, "nurture_schedule_item_id", None):
        item = db.query(NurtureScheduleItem).filter(NurtureScheduleItem.id == row.nurture_schedule_item_id).first()
        if item:
            now = datetime.utcnow()
            if payload.status == "running":
                item.status = "running"
                item.started_at = item.started_at or now
            elif payload.status in ("success", "failed", "cancelled"):
                item.status = payload.status
                item.finished_at = now
                item.last_error_code = (payload.error_code or "")[:64] or None
                item.last_error_message = (payload.error_message or "")[:5000] or None
            db.add(item)

            binding = db.query(NurtureBinding).filter(NurtureBinding.id == item.binding_id).first()
            if binding and payload.status in ("success", "failed"):
                metrics = payload.metrics if isinstance(payload.metrics, dict) else {}
                karma_delta = int(metrics.get("karma_delta") or (1 if payload.status == "success" else 0))
                if payload.status == "success":
                    binding.current_karma = max(0, int(binding.current_karma or 0) + max(0, karma_delta))
                    binding.risk_score = max(0, int(binding.risk_score or 0) - 2)
                    if binding.current_karma >= int(binding.target_karma or 0):
                        binding.phase = "post_ready"
                        binding.eligible_for_posting = True
                    elif binding.current_karma >= 20:
                        binding.phase = "engage"
                    elif binding.current_karma >= 8:
                        binding.phase = "steady"
                    else:
                        binding.phase = "warmup"
                    if binding.account_health in {"warning", "restricted"} and binding.risk_score < 40:
                        binding.account_health = "healthy"
                    binding.next_action_at = now + timedelta(hours=4)
                else:
                    binding.risk_score = min(100, int(binding.risk_score or 0) + 12)
                    binding.last_incident_code = (payload.error_code or "task_failed")[:64]
                    binding.last_incident_at = now
                    if binding.risk_score >= 90:
                        binding.account_health = "locked"
                        binding.automation_mode = "paused"
                        binding.status = "paused"
                        binding.next_action_at = now + timedelta(hours=72)
                    elif binding.risk_score >= 70:
                        binding.account_health = "restricted"
                        binding.automation_mode = "read_only"
                        binding.next_action_at = now + timedelta(hours=24)
                    else:
                        binding.account_health = "warning"
                        binding.automation_mode = "conservative"
                        binding.next_action_at = now + timedelta(hours=12)
                db.add(binding)

    db.commit()
    return {"detail": "ok", "task_status": row.status, "execution_id": execution.id}


class AnalyzeIn(BaseModel):
    platform: str = "reddit"
    days: int = Field(default=7, ge=1, le=90)


@router.post("/analyze", summary="触发风控分析（用户态）")
def trigger_analyze(
    payload: AnalyzeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = analyze_risk(
        db=db,
        user_id=current_user.id,
        platform=payload.platform,
        days=payload.days,
    )
    return {
        "id": report.id,
        "platform": report.platform,
        "summary": report.summary,
        "findings": report.findings,
        "created_at": report.created_at.isoformat() if report.created_at else "",
    }


class GenerateStrategyIn(BaseModel):
    category: str = Field(default="general", max_length=64)
    niche: str = Field(default="general", max_length=64)
    name: Optional[str] = Field(default=None, max_length=128)


@router.post("/strategies/generate", summary="生成策略（用户态）")
def trigger_generate_strategy(
    payload: GenerateStrategyIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cfg = generate_strategy(
        db=db,
        user_id=current_user.id,
        category=payload.category,
        niche=payload.niche,
        name=payload.name,
    )
    return {
        "id": cfg.id,
        "name": cfg.name,
        "category": cfg.category,
        "config": cfg.config,
        "created_at": cfg.created_at.isoformat() if cfg.created_at else "",
    }


@router.get("/strategies", summary="策略列表（用户态）")
def list_strategies(
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(RedditStrategyConfig).filter(RedditStrategyConfig.user_id == current_user.id)
    if category:
        q = q.filter(RedditStrategyConfig.category == category.strip())
    rows = q.order_by(RedditStrategyConfig.updated_at.desc()).offset(max(0, offset)).limit(min(max(1, limit), 200)).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "category": r.category,
            "config": r.config,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        }
        for r in rows
    ]


@router.get("/reports", summary="风控报告列表（用户态）")
def list_risk_reports(
    platform: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(RiskAnalysisReport).filter(RiskAnalysisReport.user_id == current_user.id)
    if platform:
        q = q.filter(RiskAnalysisReport.platform == platform.strip())
    rows = q.order_by(RiskAnalysisReport.created_at.desc()).offset(max(0, offset)).limit(min(max(1, limit), 100)).all()
    return [
        {
            "id": r.id,
            "platform": r.platform,
            "summary": r.summary[:500] + "..." if r.summary and len(r.summary) > 500 else (r.summary or ""),
            "findings": r.findings,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]

