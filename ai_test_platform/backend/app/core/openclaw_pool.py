"""OpenClaw 实例池：用户注册后自动分配实例绑定。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import OpenClawInstance, UserOpenClawBinding


def get_user_binding(db: Session, user_id: int) -> Optional[UserOpenClawBinding]:
    return (
        db.query(UserOpenClawBinding)
        .filter(UserOpenClawBinding.user_id == user_id)
        .first()
    )


def assign_instance_if_needed(db: Session, user_id: int) -> Optional[UserOpenClawBinding]:
    """
    为用户分配实例（若尚未绑定）。
    选取策略：enabled 且未超 max_users 的实例中，current_users 最少优先。
    """
    existing = get_user_binding(db, user_id)
    if existing:
        return existing

    candidate = (
        db.query(OpenClawInstance)
        .filter(
            OpenClawInstance.enabled.is_(True),
            or_(
                OpenClawInstance.max_users.is_(None),
                OpenClawInstance.current_users < OpenClawInstance.max_users,
            ),
        )
        .order_by(OpenClawInstance.current_users.asc(), OpenClawInstance.id.asc())
        .first()
    )
    if not candidate:
        return None

    agent_id = (candidate.default_agent_id or "main").strip() or "main"
    binding = UserOpenClawBinding(
        user_id=user_id,
        instance_id=candidate.id,
        agent_id=agent_id,
        status="assigned",
    )
    candidate.current_users = int(candidate.current_users or 0) + 1
    db.add(candidate)
    db.add(binding)
    return binding


def release_binding_user_count(db: Session, binding: UserOpenClawBinding) -> None:
    """当绑定被迁移/禁用时，回收实例 current_users 计数（最小到 0）。"""
    ins = db.query(OpenClawInstance).filter(OpenClawInstance.id == binding.instance_id).first()
    if not ins:
        return
    current = int(ins.current_users or 0)
    ins.current_users = current - 1 if current > 0 else 0
    db.add(ins)
