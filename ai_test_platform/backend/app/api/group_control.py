from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db import get_db
from ..core.reddit_ai import analyze_risk, generate_strategy
from ..models import (
    ControlAgent,
    ControlTask,
    MobileDevice,
    RedditStrategyConfig,
    RiskAnalysisReport,
    TaskExecution,
    TaskExecutionLog,
    User,
)
from .auth import get_current_user


router = APIRouter(prefix="/group-control", tags=["group-control"])


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


@router.get("/devices", summary="设备列表（用户态）")
def list_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    rows = db.query(MobileDevice).order_by(MobileDevice.updated_at.desc()).all()
    return [
        {
            "id": r.id,
            "serial": r.serial,
            "alias": r.alias,
            "platform": r.platform,
            "agent_id": r.agent_id,
            "adb_status": r.adb_status,
            "appium_status": r.appium_status,
            "meta": r.meta,
            "account_attrs": r.account_attrs if hasattr(r, "account_attrs") else None,
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


@router.post("/tasks", summary="创建群控任务（用户态）")
def create_task(
    payload: CreateTaskIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = ControlTask(
        user_id=current_user.id,
        title=payload.title.strip(),
        platform=(payload.platform or "reddit").strip() or "reddit",
        task_type=(payload.task_type or "reddit_flow").strip() or "reddit_flow",
        payload=payload.payload,
        target_device_id=payload.target_device_id,
        device_filter=payload.device_filter,
        priority=payload.priority,
        max_retries=payload.max_retries,
        status="pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "status": row.status}


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
    return [
        {
            "id": r.id,
            "title": r.title,
            "platform": r.platform,
            "task_type": r.task_type,
            "status": r.status,
            "target_device_id": r.target_device_id,
            "device_filter": getattr(r, "device_filter", None),
            "assigned_agent_id": r.assigned_agent_id,
            "assigned_device_id": r.assigned_device_id,
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
    return {
        "task": {
            "id": row.id,
            "title": row.title,
            "platform": row.platform,
            "task_type": row.task_type,
            "status": row.status,
            "payload": row.payload,
            "target_device_id": row.target_device_id,
            "device_filter": getattr(row, "device_filter", None),
            "assigned_agent_id": row.assigned_agent_id,
            "assigned_device_id": row.assigned_device_id,
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


@router.post("/agents/{agent_key}/next-task", summary="拉取待执行任务（Agent）")
def poll_next_task(
    agent_key: str,
    payload: AgentPollIn,
    db: Session = Depends(get_db),
    x_agent_secret: Optional[str] = Header(None, alias="X-Agent-Secret"),
):
    _ensure_agent_secret(x_agent_secret)
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
    if row.assigned_device_id:
        d = db.query(MobileDevice).filter(MobileDevice.id == row.assigned_device_id).first()
        assigned_serial = d.serial if d else None

    return {
        "task": {
            "id": row.id,
            "platform": row.platform,
            "task_type": row.task_type,
            "title": row.title,
            "payload": row.payload,
            "assigned_device_id": row.assigned_device_id,
            "assigned_device_serial": assigned_serial,
            "execution_id": execution.id,
            "lease_until": row.lease_until.isoformat() if row.lease_until else None,
        }
    }


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

