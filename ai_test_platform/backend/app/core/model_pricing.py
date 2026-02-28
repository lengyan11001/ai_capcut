"""
模型价格配置与积分计算：DB 优先，支持多模型、价格可调。
- get_model_config(db, model_id) 从 model_pricing 表读取
- compute_credits 按 token 与单价计算积分，可传入 fallback 配置（代码默认）
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import ceil
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# 与 llm_client 一致，便于统一计费
CREDITS_PER_DOLLAR: int = 1000
EXCHANGE_RATE_RMB_PER_USD: float = 7.0
MIN_CREDITS_PER_CALL: int = 100


@dataclass
class PricingConfig:
    """仅含计费所需字段，与 LLMModelConfig 兼容。"""
    input_price_per_m: float
    output_price_per_m: float
    currency: str
    margin_factor: float


def get_model_config(db: "Session", model_id: str) -> Optional[PricingConfig]:
    """
    从 model_pricing 表读取启用中的模型价格；无则返回 None，由调用方回退到代码默认。
    """
    from ..models import ModelPricing

    row = db.query(ModelPricing).filter(
        ModelPricing.model_id == model_id,
        ModelPricing.enabled.is_(True),
    ).first()
    if not row:
        return None
    return PricingConfig(
        input_price_per_m=float(row.input_price_per_m),
        output_price_per_m=float(row.output_price_per_m),
        currency=row.currency or "CNY",
        margin_factor=float(row.margin_factor),
    )


def compute_credits_with_config(
    cfg: Any,
    prompt_tokens: int,
    completion_tokens: int,
) -> int:
    """
    根据单价与 token 数计算积分。cfg 需有 input_price_per_m, output_price_per_m, currency, margin_factor。
    """
    prompt_m = prompt_tokens / 1_000_000.0
    completion_m = completion_tokens / 1_000_000.0
    cost_in_currency = prompt_m * cfg.input_price_per_m + completion_m * cfg.output_price_per_m
    currency = (getattr(cfg, "currency", None) or "CNY").upper()
    if currency == "CNY":
        dollars = cost_in_currency / EXCHANGE_RATE_RMB_PER_USD
    else:
        dollars = cost_in_currency
    raw_credits = dollars * CREDITS_PER_DOLLAR
    margin = getattr(cfg, "margin_factor", 1.0)
    charged = ceil(raw_credits * margin)
    if charged <= 0:
        charged = MIN_CREDITS_PER_CALL
    else:
        charged = max(charged, MIN_CREDITS_PER_CALL)
    return charged


def compute_credits(
    db: "Session",
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    fallback_config: Optional[Any] = None,
) -> int:
    """
    DB 优先取价，无则用 fallback_config（如 LLM_MODELS.get(model_id)），再按 token 计算积分。
    """
    cfg = get_model_config(db, model_id)
    if cfg is None:
        cfg = fallback_config
    if cfg is None:
        return 0
    return compute_credits_with_config(cfg, prompt_tokens, completion_tokens)


def add_usage_period(
    db: "Session",
    user_id: int,
    model_id: str,
    period_start: date,
    tokens_delta: int,
) -> None:
    """增加或创建当前周期的用量。period_start 建议为当月 1 号。"""
    from ..models import UsagePeriod

    if tokens_delta <= 0:
        return
    row = db.query(UsagePeriod).filter(
        UsagePeriod.user_id == user_id,
        UsagePeriod.model_id == model_id,
        UsagePeriod.period_start == period_start,
    ).first()
    if row:
        row.tokens_used += tokens_delta
    else:
        db.add(UsagePeriod(
            user_id=user_id,
            model_id=model_id,
            period_start=period_start,
            tokens_used=tokens_delta,
        ))
