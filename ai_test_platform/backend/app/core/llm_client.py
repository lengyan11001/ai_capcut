from __future__ import annotations

"""
大模型客户端与积分换算（多厂商，多模型）：
- 提供「免费模式」（no_llm）与「按具体模型计费」两种方式
- 支持为每个模型配置真实单价（阿里 / 字节 / DeepSeek / 其他）
- 统一按 tokens → 成本（美元）→ 积分 的方式结算
"""

from dataclasses import dataclass
from math import ceil
from typing import Dict, Optional, TypedDict

from openai import OpenAI

from .config import settings


class UsageLike(TypedDict, total=False):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class LLMModelConfig:
    """
    单个模型的计费与调用配置。

    注意：
    - currency 表示 input_price_per_m / output_price_per_m 的货币单位（USD 或 CNY）
    - model 为发送给底层 OpenAI 兼容端点的模型名
    """

    id: str
    provider: str
    model: str
    display_name: str
    currency: str  # "USD" 或 "CNY"
    input_price_per_m: float
    output_price_per_m: float
    margin_factor: float  # 毛利系数，例如 1.5 表示在成本上乘以 1.5


# 统一积分换算：1 美元 ≈ 1000 积分
CREDITS_PER_DOLLAR: int = 1000

# 汇率估算：1 美元 ≈ 7 元人民币（仅用于把人民币价格换算为等价美元成本）
EXCHANGE_RATE_RMB_PER_USD: float = 7.0

# 单次调用的最低扣费，避免超小请求近似免费
MIN_CREDITS_PER_CALL: int = 100


# 可用模型清单：
# - 这里的价格为「模型官方人民币价格」按汇率折算成「等价美元成本」时使用
# - 用户可以在前端选择这些模型，后端按此表计算积分
LLM_MODELS: Dict[str, LLMModelConfig] = {
    # 阿里云 · 通义千问：Qwen-Turbo（便宜档，推理快）
    "aliyun:qwen-turbo": LLMModelConfig(
        id="aliyun:qwen-turbo",
        provider="aliyun",
        model="qwen-turbo",
        display_name="阿里 · 通义 Qwen-Turbo",
        currency="CNY",
        input_price_per_m=0.3,  # 0.0003 元 / 1K → 0.3 元 / 1M
        output_price_per_m=0.6,  # 0.0006 元 / 1K → 0.6 元 / 1M
        margin_factor=1.5,
    ),
    # 阿里云 · 通义千问：Qwen-Plus（中档/主力）
    "aliyun:qwen-plus": LLMModelConfig(
        id="aliyun:qwen-plus",
        provider="aliyun",
        model="qwen-plus",
        display_name="阿里 · 通义 Qwen-Plus",
        currency="CNY",
        input_price_per_m=0.8,
        output_price_per_m=2.0,
        margin_factor=1.5,
    ),
    # 火山引擎 · 豆包：Flash 轻量模型
    "volc:doubao-flash": LLMModelConfig(
        id="volc:doubao-flash",
        provider="volcengine",
        model="doubao-flash",
        display_name="字节 · 豆包 Flash",
        currency="CNY",
        input_price_per_m=0.15,
        output_price_per_m=1.5,
        margin_factor=1.5,
    ),
    # DeepSeek · Chat
    "deepseek:chat": LLMModelConfig(
        id="deepseek:chat",
        provider="deepseek",
        model="deepseek-chat",
        display_name="DeepSeek Chat",
        currency="USD",
        input_price_per_m=0.28,
        output_price_per_m=0.42,
        margin_factor=1.5,
    ),
}


def is_llm_enabled() -> bool:
    """
    当前是否已配置底层 OpenAI 兼容端点 API Key。

    说明：
    - 这里仅检查 settings.openai_api_key 是否存在；
    - 实际上你可以在 openai_base_url 里挂接任意兼容端点，
      例如阿里/字节/DeepSeek 的 OpenAI 兼容网关。
    """
    return bool(settings.openai_api_key)


# 大模型单次请求最长等待时间（秒），避免一直 pending
LLM_REQUEST_TIMEOUT: float = 120.0


def _get_client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("未配置 OPENAI_API_KEY，无法使用 LLM 功能")
    kwargs: Dict[str, object] = {"api_key": settings.openai_api_key, "timeout": LLM_REQUEST_TIMEOUT}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


def _get_model_config(model_id: str) -> Optional[LLMModelConfig]:
    return LLM_MODELS.get(model_id)


def estimate_credits_for_usage(
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> int:
    """
    根据实际/预估的 tokens 计算本次调用需要的积分。

    - model_id 为具体模型 ID，例如 aliyun:qwen-turbo、volc:doubao-flash 等
    - 若希望「免费模式」，上层不应调用本函数，而是直接视为 0 积分
    """
    cfg = _get_model_config(model_id)
    if not cfg:
        # 未知模型，保守地视为不计费；上层可选择拒绝这类 model_id
        return 0

    prompt_m = prompt_tokens / 1_000_000.0
    completion_m = completion_tokens / 1_000_000.0

    # 先按模型本币种算出成本，再统一折算为美元
    cost_in_currency = prompt_m * cfg.input_price_per_m + completion_m * cfg.output_price_per_m
    if cfg.currency.upper() == "CNY":
        dollars = cost_in_currency / EXCHANGE_RATE_RMB_PER_USD
    else:
        dollars = cost_in_currency

    raw_credits = dollars * CREDITS_PER_DOLLAR
    charged = ceil(raw_credits * cfg.margin_factor)
    if charged <= 0:
        charged = MIN_CREDITS_PER_CALL
    else:
        charged = max(charged, MIN_CREDITS_PER_CALL)
    return charged


def rough_token_estimate_for_apis(
    api_count: int,
) -> UsageLike:
    """
    按接口数量粗略估算一次“从文档生成用例”的 tokens 消耗。

    经验规则（可以后续根据实际统计调整）：
    - prompt:
      - 固定开销：1500 tokens（系统提示词 + 说明）
      - 每个接口：约 300 tokens（路径/方法/参数等）
    - completion:
      - 每个接口：约 500 tokens（生成用例描述 + 参数/断言）
    """
    if api_count <= 0:
        return UsageLike(prompt_tokens=0, completion_tokens=0, total_tokens=0)
    prompt_tokens = 1500 + api_count * 300
    completion_tokens = api_count * 500
    total_tokens = prompt_tokens + completion_tokens
    return UsageLike(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def estimate_credits_for_apis(
    model_id: str,
    api_count: int,
) -> Dict[str, int]:
    """
    给定接口数量与模型 ID，返回一个预估的积分消耗：
    - 仅用于「规则生成」场景的预估（未用大模型设计完整用例时）
    - 真正扣费应以实际 usage 为准
    """
    usage = rough_token_estimate_for_apis(api_count)
    credits = estimate_credits_for_usage(
        model_id=model_id,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
    )
    return {
        "estimated_prompt_tokens": usage.get("prompt_tokens", 0),
        "estimated_completion_tokens": usage.get("completion_tokens", 0),
        "estimated_total_tokens": usage.get("total_tokens", 0),
        "estimated_credits": credits,
    }


def rough_token_estimate_for_openapi_doc(
    content_length: int,
    api_count: int,
) -> UsageLike:
    """
    方案二：大模型接收完整 OpenAPI 文档并输出完整用例列表时的 token 粗估。
    - prompt：系统提示词 + 整份文档（按字符数粗算 token，约 1 字符 ≈ 0.25~0.33 token）
    - completion：用例数量由模型决定，按接口数约 2~3 倍、每条用例约 400 token 估
    """
    if content_length <= 0 and api_count <= 0:
        return UsageLike(prompt_tokens=0, completion_tokens=0, total_tokens=0)
    system_and_prefix = 1200
    # 文档截断上限 120000 字符，按 1 字符 ≈ 0.3 token 估
    doc_tokens = min(content_length, 120000) * 3 // 10
    prompt_tokens = system_and_prefix + doc_tokens
    # 用例数未知，按 api_count * 2.5 条、每条约 400 token
    estimated_cases = max(int(api_count * 2.5), 10)
    completion_tokens = estimated_cases * 400
    total_tokens = prompt_tokens + completion_tokens
    return UsageLike(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def estimate_credits_for_openapi_doc(
    model_id: str,
    content_length: int,
    api_count: int,
) -> Dict[str, int]:
    """
    方案二（大模型设计完整用例）的积分预估：按文档长度 + 接口数估算 token，再换算积分。
    - 仅用于 estimate_only 与扣费前余额校验
    - 实际扣费仍以 API 返回的 usage 为准
    """
    usage = rough_token_estimate_for_openapi_doc(content_length, api_count)
    credits = estimate_credits_for_usage(
        model_id=model_id,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
    )
    return {
        "estimated_prompt_tokens": usage.get("prompt_tokens", 0),
        "estimated_completion_tokens": usage.get("completion_tokens", 0),
        "estimated_total_tokens": usage.get("total_tokens", 0),
        "estimated_credits": credits,
    }


def call_llm(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: Optional[int] = None,
) -> Dict[str, object]:
    """
    实际调用 OpenAI 模型，并返回：
    - content: str
    - usage: {prompt_tokens, completion_tokens, total_tokens}
    - credits_used: int（按真实 usage 换算）
    - max_tokens: 可选，不传则用接口默认；生成大量用例时建议传 16384 或 32768 避免截断
    """
    cfg = _get_model_config(model_id)
    if not cfg:
        raise ValueError(f"不支持的模型 ID: {model_id}")

    client = _get_client()
    create_kwargs: Dict[str, object] = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }
    if max_tokens is not None:
        create_kwargs["max_tokens"] = max_tokens
    try:
        resp = client.chat.completions.create(**create_kwargs)
    except Exception as e:
        err_msg = str(e).strip() or getattr(e, "message", "")
        raise RuntimeError(f"大模型接口调用失败：{err_msg}") from e

    if not getattr(resp, "choices", None) or len(resp.choices) == 0:
        raise RuntimeError("大模型返回为空（无 choices），请检查模型名与 API 配置")

    choice = resp.choices[0]
    content = (getattr(choice, "message", None) and getattr(choice.message, "content", None) or "") or ""
    content = (content if isinstance(content, str) else "").strip()
    usage_raw = getattr(resp, "usage", None)
    prompt_tokens = int(getattr(usage_raw, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage_raw, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage_raw, "total_tokens", 0) or (prompt_tokens + completion_tokens))

    credits_used = estimate_credits_for_usage(
        model_id=model_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )

    return {
        "content": content,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
        "credits_used": credits_used,
    }


def public_llm_pricing() -> Dict[str, object]:
    """
    供 /auth/pricing 等对外返回的 LLM 价格信息（不含敏感配置）。

    结构示例：
    {
      "enabled": true,
      "credits_per_dollar": 1000,
      "min_credits_per_call": 100,
      "models": {
        "aliyun:qwen-turbo": {
          "provider": "aliyun",
          "display_name": "...",
          "currency": "CNY",
          "input_price_per_m": ...,
          "output_price_per_m": ...,
          "margin_factor": ...,
          "estimated_credits_per_100k_tokens": ...
        },
        ...
      }
    }
    """
    out: Dict[str, object] = {
        "enabled": is_llm_enabled(),
        "credits_per_dollar": CREDITS_PER_DOLLAR,
        "min_credits_per_call": MIN_CREDITS_PER_CALL,
        "models": {},
    }
    # 额外提供一个「按 100K tokens 估算」的参考价格，便于前端展示
    sample_tokens = rough_token_estimate_for_apis(api_count=1)
    base_prompt = sample_tokens.get("prompt_tokens", 0)
    base_completion = sample_tokens.get("completion_tokens", 0)

    provider_filter = (settings.openai_provider or "").strip().lower() or None
    for model_id, cfg in LLM_MODELS.items():
        if provider_filter and cfg.provider != provider_filter:
            continue
        est_credits = estimate_credits_for_usage(
            model_id=model_id,
            prompt_tokens=base_prompt,
            completion_tokens=base_completion,
        )
        out["models"][model_id] = {
            "provider": cfg.provider,
            "display_name": cfg.display_name,
            "model": cfg.model,
            "currency": cfg.currency,
            "input_price_per_m": cfg.input_price_per_m,
            "output_price_per_m": cfg.output_price_per_m,
            "margin_factor": cfg.margin_factor,
            "estimated_credits_per_100k_tokens": est_credits,
        }
    return out

