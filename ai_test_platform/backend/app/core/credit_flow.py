"""积分资金流水：统一记录扣费、退款、充值，便于对账与展示"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ..models import CreditFlow, User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def add_credit_flow(
    db: "Session",
    user: User,
    flow_type: str,
    amount: int,
    description: str,
    related_type: Optional[str] = None,
    related_id: Optional[int] = None,
) -> None:
    """
    记录一笔积分流水并更新用户余额。
    - flow_type: deduct（扣费）| refund（退款）| recharge（充值）
    - amount: 正数。deduct 时从余额扣除 amount；refund/recharge 时向余额增加 amount
    """
    if amount <= 0:
        return
    if flow_type == "deduct":
        user.credits -= amount
    else:
        user.credits += amount
    balance_after = user.credits
    flow = CreditFlow(
        user_id=user.id,
        flow_type=flow_type,
        amount=amount,
        balance_after=balance_after,
        description=description,
        related_type=related_type,
        related_id=related_id,
    )
    db.add(user)
    db.add(flow)
