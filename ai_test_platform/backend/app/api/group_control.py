from __future__ import annotations

import json
import logging
import re
import threading
from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, status
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
    DailyReport,
    MobileDevice,
    RedditAccountAsset,
    RedditPolicySnapshot,
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


def _get_llm_endpoints() -> list[dict[str, str]]:
    """Return ordered list of LLM endpoints for fallback."""
    endpoints: list[dict[str, str]] = []
    raw = (settings.nurture_llm_endpoints or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                for ep in parsed:
                    if isinstance(ep, dict) and ep.get("base_url") and ep.get("api_key"):
                        endpoints.append({
                            "base_url": ep["base_url"].strip().rstrip("/"),
                            "api_key": ep["api_key"].strip(),
                            "label": ep.get("label", ep["base_url"]),
                        })
        except Exception:
            logger.warning("Failed to parse NURTURE_LLM_ENDPOINTS")
    base = (settings.nurture_llm_base_url or "").strip().rstrip("/")
    key = (settings.nurture_llm_api_key or "").strip()
    if base and key:
        already = any(ep["base_url"] == base for ep in endpoints)
        if not already:
            endpoints.append({"base_url": base, "api_key": key, "label": base})
    return endpoints


_BILLING_ERROR_KEYWORDS = [
    "billing", "insufficient", "balance", "quota", "credit", "payment",
    "exceeded", "limit reached", "top up", "run out", "402",
]


def _is_billing_error(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _BILLING_ERROR_KEYWORDS)


def _call_llm_with_fallback(
    model: str,
    messages: list[dict],
    temperature: float = 0.2,
    timeout_read: float = 600.0,
) -> dict[str, Any]:
    """
    Call LLM with automatic endpoint fallback.
    Returns {"ok": True, "data": <api_response>, "endpoint": "..."} on success,
    or {"ok": False, "error": "...", "tried": [...]} on all-fail.
    """
    endpoints = _get_llm_endpoints()
    if not endpoints:
        return {"ok": False, "error": "未配置任何 LLM 通道", "tried": []}
    tried: list[str] = []
    last_error = ""
    for ep in endpoints:
        label = ep["label"]
        tried.append(label)
        try:
            timeout = httpx.Timeout(connect=30.0, read=timeout_read, write=30.0, pool=30.0)
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    f"{ep['base_url']}/chat/completions",
                    headers={"Authorization": f"Bearer {ep['api_key']}", "Content-Type": "application/json"},
                    json={"model": model, "messages": messages, "temperature": temperature},
                )
                if resp.status_code >= 300:
                    error_text = resp.text[:300] if resp.text else str(resp.status_code)
                    if _is_billing_error(error_text):
                        logger.warning("LLM endpoint %s billing error, trying next: %s", label, error_text[:120])
                        last_error = f"[{label}] 余额不足: {error_text[:120]}"
                        continue
                    last_error = f"[{label}] HTTP {resp.status_code}: {error_text[:120]}"
                    continue
                data = resp.json() if resp.content else {}
                if data.get("error"):
                    err_msg = str(data["error"].get("message", ""))[:200]
                    if _is_billing_error(err_msg):
                        logger.warning("LLM endpoint %s billing error in body, trying next: %s", label, err_msg[:120])
                        last_error = f"[{label}] 余额不足: {err_msg[:120]}"
                        continue
                    last_error = f"[{label}] API error: {err_msg[:120]}"
                    continue
                return {"ok": True, "data": data, "endpoint": label}
        except httpx.TimeoutException:
            last_error = f"[{label}] 请求超时"
            logger.warning("LLM endpoint %s timeout, trying next", label)
            continue
        except Exception as exc:
            last_error = f"[{label}] {exc}"
            logger.warning("LLM endpoint %s failed: %s, trying next", label, exc)
            continue
    return {"ok": False, "error": last_error, "tried": tried}


NURTURE_MODEL_OPTIONS = [
    {"id": "deepseek-chat",               "name": "DeepSeek Chat",          "tier": "basic",   "speed": "fast"},
    {"id": "deepseek-v3.1",               "name": "DeepSeek V3.1",          "tier": "basic",   "speed": "fast"},
    {"id": "gpt-4o-mini",                 "name": "GPT-4o Mini",            "tier": "basic",   "speed": "fast"},
    {"id": "gpt-4o",                      "name": "GPT-4o",                 "tier": "pro",     "speed": "medium"},
    {"id": "claude-sonnet-4-5-20250929",  "name": "Claude Sonnet 4.5",      "tier": "pro",     "speed": "medium"},
    {"id": "claude-sonnet-4-6",           "name": "Claude Sonnet 4.6",      "tier": "pro",     "speed": "medium"},
    {"id": "gemini-2.5-flash",            "name": "Gemini 2.5 Flash",       "tier": "basic",   "speed": "fast"},
    {"id": "gemini-2.5-pro",              "name": "Gemini 2.5 Pro",         "tier": "pro",     "speed": "medium"},
]
NURTURE_DEFAULT_MODEL = "deepseek-chat"
NURTURE_TIER_ORDER = {"basic": 0, "pro": 1}


def _user_nurture_tier(user: User) -> str:
    return getattr(user, "nurture_model_tier", None) or "basic"


def _allowed_models_for_user(user: User) -> list[dict]:
    tier = _user_nurture_tier(user)
    tier_level = NURTURE_TIER_ORDER.get(tier, 0)
    return [m for m in NURTURE_MODEL_OPTIONS if NURTURE_TIER_ORDER.get(m["tier"], 0) <= tier_level]


def _validate_model_for_user(user: User, model_id: str) -> str:
    """校验用户是否有权使用该模型，返回有效 model_id 或抛异常。"""
    if not model_id:
        return NURTURE_DEFAULT_MODEL
    allowed = {m["id"] for m in _allowed_models_for_user(user)}
    if model_id not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"模型 {model_id} 不在你的权限范围内，当前 tier: {_user_nurture_tier(user)}",
        )
    return model_id


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


def _build_nurture_prompt(
    binding: NurtureBinding,
    objective: str,
    risk_preference: str,
) -> str:
    return (
        "你是 Reddit 养号计划器。输出严格 JSON，不要 markdown。\n"
        "目标：生成仅养号（不发帖）计划，字段必须包含 plan_version, summary, plan_horizon_days, next_review_in_days, schedule。\n"
        "schedule 每项字段必须包含 day_no, seq_no, hour, minute, stage, title, payload。\n"
        "payload 必须包含 action 字段，以及该 action 对应的参数。\n\n"
        "=== 可用动作目录（只能从以下 action 中选择）===\n"
        "- browse: 滑动浏览首页/热门 Feed | 可选参数: duration_min, max_scrolls | 适用阶段: warmup,steady,engage,post_ready | 风险: low\n"
        "- search: 搜索关键词并浏览结果 | 必选参数: keyword | 可选: duration_min, max_scrolls | 适用阶段: warmup,steady,engage,post_ready | 风险: low\n"
        "- upvote: 浏览 Feed 过程中按概率随机点赞 | 可选参数: duration_min, max_actions, upvote_ratio(0-1) | 适用阶段: steady,engage,post_ready | 风险: medium\n"
        "- subscribe: 进入指定 Subreddit 并 Join | **必选参数: subreddit_name**（必须是真实存在的 Reddit 社区名，与 objective 直接相关）| 适用阶段: steady,engage,post_ready | 风险: low\n"
        "- comment: 打开帖子发表简短评论 | 可选参数: max_actions, comment_templates(字符串数组) | 适用阶段: engage,post_ready | 风险: high\n"
        "- profile_check: 进入 Profile 页读取 karma 和账号状态 | 无参数 | 适用阶段: 所有 | 风险: low\n\n"
        "=== 编排约束 ===\n"
        "1. warmup 阶段(前7天)只允许 browse/search/profile_check\n"
        "2. steady 阶段(8-20天)可增加 upvote/subscribe，upvote_ratio 不超过 0.05\n"
        "3. engage 阶段(21天+)可增加 comment，每天最多 2 条评论\n"
        "4. 每天至少安排 1 次 profile_check\n"
        "5. 单次 session 持续时间 duration_min 建议 5-15 分钟\n"
        "6. plan_horizon_days 固定为 14，next_review_in_days 取 1-3\n\n"
        "=== 内容方向要求（极其重要）===\n"
        f"养号方向(objective)：{objective}\n"
        "你必须严格围绕上述 objective 来生成所有内容参数，具体要求：\n"
        "A. search 的 keyword 必须与 objective 直接相关，使用该领域的真实英文搜索词（Reddit 是英文平台），"
        "每次搜索词要有变化但都聚焦在 objective 领域内，不要用泛泛的通用词\n"
        "B. subscribe 的 subreddit_name 必须填写，且必须是与 objective 相关的、真实存在的 Reddit 社区名（不带 r/ 前缀），"
        "例如该领域的爱好者社区、讨论区、交易区等\n"
        "C. 不要因为 objective 涉及成人/敏感内容就回避或替换为无关的安全词，"
        "Reddit 本身允许 NSFW 内容，养号就是要建立与 objective 一致的兴趣画像\n"
        "D. comment_templates 的内容也应贴合 objective 领域的正常讨论风格\n\n"
        f"其他参数：risk_preference={risk_preference}, current_phase={binding.phase}, "
        f"current_karma={binding.current_karma}, target_karma={binding.target_karma}, "
        f"account_health={binding.account_health}, mode={binding.automation_mode}。"
    )


def _build_eval_prompt(objective: str, plan_json: dict) -> str:
    """构建计划评分 prompt，让 AI 自评并给出优化建议。"""
    plan_str = json.dumps(plan_json, ensure_ascii=False, indent=None)
    return (
        "你是 Reddit 养号计划质量审核员。对以下养号计划进行评分并给出改进建议。\n"
        "输出严格 JSON，不要 markdown。\n\n"
        f"养号方向(objective)：{objective}\n\n"
        f"待评审计划：\n{plan_str}\n\n"
        "=== 评分维度（每项 0-100 分）===\n"
        "1. keyword_relevance: search 关键词与 objective 的贴合度（关键词是否精准聚焦在该领域，而非泛泛通用词）\n"
        "2. subreddit_relevance: subscribe 的 subreddit_name 与 objective 的匹配度（是否是真实存在的相关社区）\n"
        "3. stage_compliance: 阶段规则遵守情况（warmup 不出现 upvote/subscribe/comment 等）\n"
        "4. rhythm_naturalness: 时间分布自然度（是否像真人使用，间隔合理，时段分散）\n"
        "5. risk_control: 风险控制（upvote_ratio 渐进、高风险动作占比）\n"
        "6. content_diversity: 内容丰富度（关键词是否有变化、动作组合是否多样）\n\n"
        "=== 输出格式 ===\n"
        "{\n"
        '  "scores": {\n'
        '    "keyword_relevance": <0-100>,\n'
        '    "subreddit_relevance": <0-100>,\n'
        '    "stage_compliance": <0-100>,\n'
        '    "rhythm_naturalness": <0-100>,\n'
        '    "risk_control": <0-100>,\n'
        '    "content_diversity": <0-100>\n'
        "  },\n"
        '  "total_score": <加权平均, 0-100>,\n'
        '  "verdict": "pass" 或 "needs_improvement",\n'
        '  "issues": ["具体问题1", "具体问题2", ...],\n'
        '  "suggestions": ["改进建议1", "改进建议2", ...]\n'
        "}\n\n"
        "total_score 加权：keyword_relevance 25%, subreddit_relevance 20%, stage_compliance 20%, "
        "rhythm_naturalness 15%, risk_control 10%, content_diversity 10%。\n"
        "total_score >= 80 时 verdict 为 pass，否则为 needs_improvement。"
    )


def _build_refine_prompt(objective: str, plan_json: dict, eval_result: dict) -> str:
    """构建计划优化 prompt，把评分反馈给 AI 让其改进。"""
    plan_str = json.dumps(plan_json, ensure_ascii=False, indent=None)
    issues = eval_result.get("issues", [])
    suggestions = eval_result.get("suggestions", [])
    scores = eval_result.get("scores", {})
    return (
        "你是 Reddit 养号计划器。上一版计划被质量审核评为需要改进。\n"
        "请根据以下反馈优化计划，输出严格 JSON（与原计划相同格式），不要 markdown。\n\n"
        f"养号方向(objective)：{objective}\n\n"
        f"上一版计划：\n{plan_str}\n\n"
        f"评分详情：{json.dumps(scores, ensure_ascii=False)}\n"
        f"发现的问题：{json.dumps(issues, ensure_ascii=False)}\n"
        f"改进建议：{json.dumps(suggestions, ensure_ascii=False)}\n\n"
        "要求：\n"
        "1. 针对上述问题逐一修正\n"
        "2. 保持整体结构不变（plan_version, summary, plan_horizon_days, next_review_in_days, schedule）\n"
        "3. subscribe 必须有 subreddit_name，search 的 keyword 必须与 objective 直接相关\n"
        "4. 不要回避敏感内容方向，Reddit 允许 NSFW\n"
        "5. 输出完整的优化后计划 JSON"
    )


def _extract_llm_content(data: dict) -> str:
    choices = data.get("choices") or []
    if choices and isinstance(choices[0], dict):
        msg = choices[0].get("message") or {}
        return str(msg.get("content") or "")
    return ""


def _parse_json_from_llm(content: str) -> Optional[dict]:
    raw = content.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*", "", raw).strip()
        raw = raw[:-3].strip() if raw.endswith("```") else raw
    return json.loads(raw)


def _call_llm_for_eval(
    plan_json: dict,
    objective: str,
    model: str,
) -> Optional[dict[str, Any]]:
    """调用 LLM 对计划评分（不 fallback，与计划生成用同一通道）。"""
    prompt = _build_eval_prompt(objective, plan_json)
    result = _call_llm_single_endpoint(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        timeout_read=300.0,
    )
    if not result["ok"]:
        logger.warning("eval LLM failed: %s", result["error"])
        return None
    try:
        content = _extract_llm_content(result["data"])
        return _parse_json_from_llm(content)
    except Exception as exc:
        logger.warning("eval LLM parse failed: %s", exc)
        return None


def _call_llm_for_refine(
    plan_json: dict,
    eval_result: dict,
    objective: str,
    model: str,
) -> Optional[dict[str, Any]]:
    """调用 LLM 优化计划（不 fallback，与计划生成用同一通道）。"""
    prompt = _build_refine_prompt(objective, plan_json, eval_result)
    result = _call_llm_single_endpoint(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        timeout_read=600.0,
    )
    if not result["ok"]:
        logger.warning("refine LLM failed: %s", result["error"])
        return None
    try:
        content = _extract_llm_content(result["data"])
        return _parse_llm_plan_response(content)
    except Exception as exc:
        logger.warning("refine LLM parse failed: %s", exc)
        return None


def _parse_llm_plan_response(content: str) -> Optional[dict[str, Any]]:
    """从 LLM 返回的文本中解析出 plan JSON。"""
    raw = content.strip()
    if not raw:
        return None
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*", "", raw).strip()
        raw = raw[:-3].strip() if raw.endswith("```") else raw
    try:
        plan = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(plan, dict):
        return None
    if not isinstance(plan.get("schedule"), list):
        return None
    return plan


def _call_llm_single_endpoint(
    model: str,
    messages: list[dict],
    temperature: float = 0.2,
    timeout_read: float = 600.0,
) -> dict[str, Any]:
    """
    Call LLM using the primary endpoint only (no fallback).
    Returns {"ok": True, "data": ..., "endpoint": ...} or {"ok": False, "error": "..."}.
    """
    endpoints = _get_llm_endpoints()
    if not endpoints:
        return {"ok": False, "error": "未配置 LLM 通道"}
    ep = endpoints[0]
    try:
        timeout = httpx.Timeout(connect=30.0, read=timeout_read, write=30.0, pool=30.0)
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{ep['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {ep['api_key']}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": temperature},
            )
            if resp.status_code >= 300:
                error_text = resp.text[:300] if resp.text else str(resp.status_code)
                return {"ok": False, "error": f"模型返回错误 ({resp.status_code}): {error_text[:200]}"}
            data = resp.json() if resp.content else {}
            if data.get("error"):
                err_msg = str(data["error"].get("message", "unknown error"))[:200]
                return {"ok": False, "error": f"模型错误: {err_msg}"}
            return {"ok": True, "data": data, "endpoint": ep["label"]}
    except httpx.TimeoutException:
        return {"ok": False, "error": "请求超时，模型响应时间过长"}
    except Exception as exc:
        return {"ok": False, "error": f"调用失败: {exc}"}


def _call_direct_llm_for_plan(
    binding: NurtureBinding,
    objective: str,
    risk_preference: str,
    model_override: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """直接调用 LLM 生成计划（不 fallback，用户选的模型报错就报错）。"""
    endpoints = _get_llm_endpoints()
    if not endpoints:
        return None
    model = (model_override or settings.nurture_llm_model or NURTURE_DEFAULT_MODEL).strip()
    prompt = _build_nurture_prompt(binding, objective, risk_preference)
    result = _call_llm_single_endpoint(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        timeout_read=600.0,
    )
    if not result["ok"]:
        return {"_error": True, "_error_msg": f"AI 模型 ({model}) {result['error']}"}
    data = result["data"]
    content = _extract_llm_content(data)
    plan = _parse_llm_plan_response(content)
    if plan:
        resp_model = str(data.get("model") or model)
        plan["_source"] = "direct_llm"
        plan["_model"] = resp_model
        plan["_endpoint"] = result.get("endpoint", "")
    return plan


def _call_openclaw_for_plan(
    user: User,
    binding: NurtureBinding,
    objective: str,
    risk_preference: str,
    model_override: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    生成养号计划：优先走直接 LLM 端点（ephone.chat 等），
    失败再走 OpenClaw 网关。
    """
    plan = _call_direct_llm_for_plan(binding, objective, risk_preference, model_override=model_override)
    if plan:
        if plan.get("_error"):
            return plan
        logger.info("nurture plan generated via direct LLM (%s)", plan.get("_model"))
        return plan

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
    prompt = _build_nurture_prompt(binding, objective, risk_preference)
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
            plan = _parse_llm_plan_response(content)
            if plan:
                resp_model = str(data.get("model") or "openclaw")
                plan["_source"] = "openclaw"
                plan["_model"] = resp_model
                plan["_endpoint"] = base.rstrip("/")
            return plan
    except Exception:
        return None


def _apply_daily_strategy_to_plans(db: Session, snap: NurtureStrategySnapshot) -> None:
    """
    根据每日策略快照的 recommendations，对未来未执行的养号计划做轻量自动调参。

    设计目标：
    - 如果失败率升高（severity 提升），则收缩后续任务节奏，而不是一次性生成 30 天后永远不变。
    - 仅调整「未来」的 NurtureScheduleItem，避免影响已派发/执行中的任务。
    - 调整范围控制在安全参数上（upvote_ratio、执行间隔、automation_mode）。
    """
    recs: dict[str, Any] = snap.recommendations or {}
    reduce_upvote_by = float(recs.get("reduce_upvote_ratio_by") or 0.0)
    cooldown_minutes = int(recs.get("increase_cooldown_minutes") or 0)
    switch_mode = str(recs.get("switch_mode") or "").strip()

    if not reduce_upvote_by and not cooldown_minutes and not switch_mode:
        return

    now = datetime.utcnow()

    # 1) 调整未来未执行的 schedule items（所有用户的 approved/active 计划）
    plan_ids = [
        p.id
        for p in db.query(NurturePlan)
        .filter(NurturePlan.status.in_(["approved", "active"]))
        .all()
    ]
    if plan_ids:
        items = (
            db.query(NurtureScheduleItem)
            .filter(
                NurtureScheduleItem.plan_id.in_(plan_ids),
                NurtureScheduleItem.status == "scheduled",
                NurtureScheduleItem.scheduled_at > now,
            )
            .all()
        )
    else:
        items = []

    for it in items:
        payload = dict(it.payload or {})
        action = str(payload.get("action") or "").strip()

        # 减少未来 upvote 任务的点赞比例
        if reduce_upvote_by and action == "upvote":
            try:
                cur_ratio = float(payload.get("upvote_ratio") or 0.05)
            except Exception:
                cur_ratio = 0.05
            new_ratio = max(0.0, cur_ratio - reduce_upvote_by)
            payload["upvote_ratio"] = new_ratio

        it.payload = payload

        # 增加冷却：简单处理为整体向后平移 scheduled_at，避免过密
        if cooldown_minutes:
            it.scheduled_at = it.scheduled_at + timedelta(minutes=cooldown_minutes)

        db.add(it)

    # 2) 如果需要，整体切到 conservative 模式：调整绑定的 automation_mode
    if switch_mode:
        binds = (
            db.query(NurtureBinding)
            .filter(NurtureBinding.status == "active")
            .all()
        )
        for b in binds:
            # 只在推荐 conservative 时调整；其他值预留未来扩展
            if switch_mode == "conservative":
                b.automation_mode = "conservative"
                db.add(b)

    db.commit()


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

    # 应用每日策略对后续计划/任务做自动轻量收敛
    try:
        _apply_daily_strategy_to_plans(db, snap)
    except Exception:
        logger.exception("apply_daily_strategy_to_plans failed for snapshot=%s", snap.id)

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
        if not plan or not binding:
            item.status = "skipped"
            item.last_error_code = "plan_inactive_or_binding_missing"
            item.last_error_message = "plan or binding missing"
            item.finished_at = now
            db.add(item)
            continue
        if plan.status in {"draft", "generating", "gen_failed"}:
            continue
        if plan.status not in {"approved", "active"}:
            item.status = "skipped"
            item.last_error_code = "plan_inactive"
            item.last_error_message = f"plan status={plan.status}"
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

        # 根据绑定设备的平台自动选择任务平台：
        # - android -> reddit
        # - ios     -> reddit_ios
        task_platform = "reddit"
        if binding.device_id:
            dev = db.query(MobileDevice).filter(MobileDevice.id == binding.device_id).first()
            if dev:
                plat = (dev.platform or "android").strip().lower()
                if plat == "ios":
                    task_platform = "reddit_ios"

        row = ControlTask(
            user_id=item.user_id,
            title=item.title,
            platform=task_platform,
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
    device_ids = [r.id for r in rows]
    running_tasks_q = (
        db.query(ControlTask.target_device_id, func.count(ControlTask.id), func.min(ControlTask.title))
        .filter(ControlTask.target_device_id.in_(device_ids), ControlTask.status.in_(["pending", "running"]))
        .group_by(ControlTask.target_device_id)
        .all()
    ) if device_ids else []
    running_map: dict[int, tuple[int, str]] = {}
    for did, cnt, t in running_tasks_q:
        running_map[did] = (cnt, t or "")

    offline_seconds = max(int(getattr(settings, "control_agent_offline_seconds", 90) or 90), 10)
    now = datetime.utcnow()

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
            "is_online": bool(r.last_seen_at and (now - r.last_seen_at).total_seconds() <= offline_seconds),
            "online_status": "online"
            if (r.last_seen_at and (now - r.last_seen_at).total_seconds() <= offline_seconds)
            else "offline",
            "running_task_count": running_map.get(r.id, (0, ""))[0],
            "running_task_summary": running_map.get(r.id, (0, ""))[1],
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
    objective: str = Field(default="safe_growth", max_length=256)
    risk_preference: str = Field(default="conservative", max_length=32)
    start_date: Optional[str] = None
    name: Optional[str] = Field(default=None, max_length=128)
    model: Optional[str] = Field(default=None, max_length=64)


class NurturePlanGenerateByDeviceIn(BaseModel):
    device_id: int
    objective: str = Field(default="safe_growth", max_length=256)
    risk_preference: str = Field(default="conservative", max_length=32)
    start_date: Optional[str] = None
    name: Optional[str] = Field(default=None, max_length=128)
    auto_approve: bool = False
    model: Optional[str] = Field(default=None, max_length=64)


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


@router.post("/nurture/bindings/{binding_id}/reset", summary="重置养号绑定状态（用户态）")
def reset_nurture_binding(
    binding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(NurtureBinding)
        .filter(NurtureBinding.id == binding_id, NurtureBinding.user_id == current_user.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="binding not found")

    # 手动恢复到「正常可执行」状态。
    row.status = "active"
    row.account_health = "healthy"
    row.automation_mode = "normal"
    row.risk_score = 0
    row.last_incident_code = None
    row.last_incident_at = None
    row.next_action_at = None

    db.commit()
    db.refresh(row)

    return {
        "id": row.id,
        "device_id": row.device_id,
        "status": row.status,
        "account_health": row.account_health,
        "automation_mode": row.automation_mode,
        "risk_score": row.risk_score,
        "next_action_at": _iso(row.next_action_at),
    }


@router.post("/nurture/plans/generate", summary="生成养号计划草案（用户态，云端 OpenClaw）")
def generate_nurture_plan(
    payload: NurturePlanGenerateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model_id = _validate_model_for_user(current_user, payload.model or "")
    return _generate_nurture_plan_for_binding(
        db=db,
        current_user=current_user,
        binding_id=payload.binding_id,
        objective=(payload.objective or "safe_growth").strip() or "safe_growth",
        risk_preference=(payload.risk_preference or "conservative").strip() or "conservative",
        start_date=payload.start_date,
        name=payload.name,
        model=model_id,
    )


def _generate_nurture_plan_for_binding(
    db: Session,
    current_user: User,
    binding_id: int,
    objective: str,
    risk_preference: str,
    start_date: Optional[str],
    name: Optional[str],
    model: Optional[str] = None,
) -> dict[str, Any]:
    """创建 generating 状态的计划占位行，然后在后台线程中调用 LLM 填充。"""
    model = model or NURTURE_DEFAULT_MODEL
    binding = (
        db.query(NurtureBinding)
        .filter(NurtureBinding.id == binding_id, NurtureBinding.user_id == current_user.id)
        .first()
    )
    if not binding:
        raise HTTPException(status_code=404, detail="binding not found")
    if start_date:
        try:
            datetime.strptime(start_date.strip(), "%Y-%m-%d")
        except Exception:
            raise HTTPException(status_code=400, detail="start_date format must be YYYY-MM-DD")

    plan_name = (name or f"nurture-plan-binding-{binding.id}").strip() or f"nurture-plan-binding-{binding.id}"
    row = NurturePlan(
        user_id=current_user.id,
        binding_id=binding.id,
        name=plan_name,
        status="generating",
        plan_version="v1",
        approval_mode="plan_once_then_auto",
        plan_horizon_days=14,
        requires_reconfirm=False,
        summary="AI 正在生成计划…",
        objective=objective,
        last_review_at=datetime.utcnow(),
        next_review_at=datetime.utcnow() + timedelta(days=1),
        plan_json={"_status": "generating", "_model": model},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    plan_id = row.id
    user_id = current_user.id
    t = threading.Thread(
        target=_bg_generate_plan,
        args=(plan_id, user_id, binding_id, objective, risk_preference, start_date, model),
        daemon=True,
    )
    t.start()

    return {
        "id": row.id,
        "binding_id": row.binding_id,
        "status": row.status,
        "approval_mode": row.approval_mode,
        "plan_horizon_days": row.plan_horizon_days,
        "summary": row.summary,
        "created_schedule_count": 0,
    }


def _bg_generate_plan(
    plan_id: int,
    user_id: int,
    binding_id: int,
    objective: str,
    risk_preference: str,
    start_date: Optional[str],
    model: str,
):
    """后台线程：调用 LLM 生成计划内容，更新数据库行。"""
    from ..db import SessionLocal

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        binding = db.query(NurtureBinding).filter(NurtureBinding.id == binding_id).first()
        plan_row = db.query(NurturePlan).filter(NurturePlan.id == plan_id).first()
        if not user or not binding or not plan_row:
            logger.error("bg_generate_plan: missing records for plan=%s", plan_id)
            return
        if plan_row.status != "generating":
            return

        eval_rounds: list[dict] = []
        max_rounds = 3
        pass_threshold = 80

        def _update_progress(stage: str, round_no: int, detail: str = ""):
            plan_row.plan_json = {
                "_status": "generating", "_model": model,
                "_stage": stage, "_round": round_no, "_detail": detail,
                "_eval_rounds": eval_rounds,
            }
            plan_row.summary = f"{stage}（第{round_no}轮）{detail}"
            plan_row.updated_at = datetime.utcnow()
            db.commit()

        _update_progress("生成计划", 1, "正在调用 AI…")

        plan_json = _call_openclaw_for_plan(
            user, binding,
            objective=objective,
            risk_preference=risk_preference,
            model_override=model,
        )

        if isinstance(plan_json, dict) and plan_json.get("_error"):
            plan_row.status = "gen_failed"
            plan_row.summary = plan_json.get("_error_msg", "模型返回错误")
            plan_row.plan_json = {"_status": "gen_failed", "_model": model, "_error_msg": plan_json.get("_error_msg", ""), "_eval_rounds": eval_rounds}
            db.commit()
            return

        if not isinstance(plan_json, dict) or not plan_json.get("schedule"):
            plan_row.status = "gen_failed"
            plan_row.summary = "AI 返回数据格式无效，请重试"
            plan_row.plan_json = {"_status": "gen_failed", "_model": model, "_error_msg": "invalid response format", "_eval_rounds": eval_rounds}
            db.commit()
            return

        for round_no in range(1, max_rounds + 1):
            _update_progress("AI 评分", round_no, "正在评估计划质量…")
            eval_result = _call_llm_for_eval(plan_json, objective, model)

            if not isinstance(eval_result, dict) or "total_score" not in eval_result:
                eval_rounds.append({
                    "round": round_no,
                    "score": None,
                    "verdict": "eval_failed",
                    "detail": "评分调用失败，跳过优化",
                    "timestamp": datetime.utcnow().isoformat(),
                })
                break

            total_score = float(eval_result.get("total_score", 0))
            scores = eval_result.get("scores", {})
            verdict = eval_result.get("verdict", "unknown")
            issues = eval_result.get("issues", [])
            suggestions = eval_result.get("suggestions", [])

            eval_rounds.append({
                "round": round_no,
                "score": total_score,
                "scores": scores,
                "verdict": verdict,
                "issues": issues,
                "suggestions": suggestions,
                "timestamp": datetime.utcnow().isoformat(),
            })

            if total_score >= pass_threshold or verdict == "pass":
                _update_progress("评分通过", round_no, f"得分 {total_score:.0f}")
                break

            if round_no >= max_rounds:
                _update_progress("达到最大轮次", round_no, f"最终得分 {total_score:.0f}")
                break

            _update_progress("优化计划", round_no + 1,
                             f"上轮得分 {total_score:.0f}，正在改进…")
            refined = _call_llm_for_refine(plan_json, eval_result, objective, model)
            if isinstance(refined, dict) and refined.get("schedule"):
                src = plan_json.get("_source", "direct_llm")
                mdl = plan_json.get("_model", model)
                ep = plan_json.get("_endpoint", "")
                refined["_source"] = src
                refined["_model"] = mdl
                refined["_endpoint"] = ep
                plan_json = refined
            else:
                eval_rounds.append({
                    "round": round_no + 1,
                    "score": None,
                    "verdict": "refine_failed",
                    "detail": "优化调用失败，使用当前版本",
                    "timestamp": datetime.utcnow().isoformat(),
                })
                break

        plan_json["_eval_rounds"] = eval_rounds

        days = int(plan_json.get("plan_horizon_days") or 14)
        if days < 1:
            days = 14
        if days > 180:
            days = 180
        schedule = plan_json.get("schedule", [])
        if not isinstance(schedule, list):
            schedule = []

        final_score = eval_rounds[-1].get("score") if eval_rounds else None
        score_summary = f" (AI评分:{final_score:.0f})" if isinstance(final_score, (int, float)) else ""
        plan_row.status = "draft"
        plan_row.plan_version = str(plan_json.get("plan_version") or "v1")
        plan_row.plan_horizon_days = days
        plan_row.summary = str(plan_json.get("summary") or "") + score_summary
        plan_row.plan_json = plan_json
        plan_row.next_review_at = datetime.utcnow() + timedelta(days=max(1, min(3, int(plan_json.get("next_review_in_days") or 1))))
        plan_row.updated_at = datetime.utcnow()

        db.query(NurtureScheduleItem).filter(NurtureScheduleItem.plan_id == plan_id).delete()

        start_dt = None
        if start_date:
            try:
                start_dt = datetime.strptime(start_date.strip(), "%Y-%m-%d")
            except Exception:
                pass
        if not start_dt:
            now = datetime.utcnow()
            start_dt = datetime(now.year, now.month, now.day)
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
                    user_id=user.id,
                    binding_id=binding_id,
                    plan_id=plan_id,
                    day_no=day_no,
                    seq_no=seq_no,
                    stage=str(item.get("stage") or binding.phase or "warmup"),
                    title=str(item.get("title") or f"nurture-day{day_no:02d}-s{seq_no}"),
                    scheduled_at=when,
                    status="scheduled",
                    payload=item.get("payload") if isinstance(item.get("payload"), dict) else {},
                )
            )
        db.commit()
        logger.info("bg_generate_plan: plan=%s completed (%s items, %d eval rounds)", plan_id, len(schedule), len(eval_rounds))
    except Exception as exc:
        logger.exception("bg_generate_plan: unexpected error for plan=%s: %s", plan_id, exc)
        try:
            plan_row = db.query(NurturePlan).filter(NurturePlan.id == plan_id).first()
            if plan_row and plan_row.status == "generating":
                plan_row.status = "gen_failed"
                plan_row.summary = f"生成异常: {str(exc)[:100]}"
                plan_row.plan_json = {"_status": "gen_failed", "_model": model, "_error_msg": str(exc)[:200]}
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


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
    binding_is_new = bind_ret.get("detail") == "created"
    model_id = _validate_model_for_user(current_user, payload.model or "")
    result = _generate_nurture_plan_for_binding(
        db=db,
        current_user=current_user,
        binding_id=binding_id,
        objective=(payload.objective or "safe_growth").strip() or "safe_growth",
        risk_preference=(payload.risk_preference or "conservative").strip() or "conservative",
        start_date=payload.start_date,
        name=payload.name,
        model=model_id,
    )
    result["device_id"] = payload.device_id
    result["binding_is_new"] = binding_is_new
    total_bindings = db.query(NurtureBinding).filter(NurtureBinding.user_id == current_user.id).count()
    result["total_bindings"] = total_bindings
    if payload.auto_approve and result.get("id"):
        _ = approve_nurture_plan(plan_id=int(result["id"]), db=db, current_user=current_user)
        result["status"] = "approved"
        result["auto_approved"] = True
    else:
        result["auto_approved"] = False
    return result


class BatchGenerateIn(BaseModel):
    device_ids: Optional[list[int]] = None

@router.post("/nurture/plans/generate-batch", summary="批量为指定/全部设备创建养号计划（用户态）")
def generate_nurture_plans_batch(
    payload: Optional[BatchGenerateIn] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed = set(_allowed_device_ids_for_user(db, current_user))
    if payload and payload.device_ids:
        device_ids = sorted(d for d in payload.device_ids if d in allowed)
    else:
        device_ids = sorted(allowed)
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

    # Enrich plans with device platform (android/ios) inferred from binding.device_id -> MobileDevice.platform
    binding_ids = {int(r.binding_id) for r in rows if getattr(r, "binding_id", None)}
    bindings = (
        db.query(NurtureBinding).filter(NurtureBinding.id.in_(binding_ids)).all() if binding_ids else []
    )
    binding_map = {b.id: b for b in bindings}
    device_ids = {b.device_id for b in bindings if getattr(b, "device_id", None)}
    devices = (
        db.query(MobileDevice).filter(MobileDevice.id.in_(device_ids)).all() if device_ids else []
    )
    device_map = {d.id: d for d in devices}

    return [
        {
            "id": r.id,
            "binding_id": r.binding_id,
            "device_id": (binding_map.get(r.binding_id).device_id if binding_map.get(r.binding_id) else None),
            "device_platform": (
                (device_map.get(binding_map.get(r.binding_id).device_id).platform)
                if (binding_map.get(r.binding_id) and device_map.get(binding_map.get(r.binding_id).device_id))
                else None
            ),
            "task_platform": (
                "reddit_ios"
                if (
                    binding_map.get(r.binding_id)
                    and device_map.get(binding_map.get(r.binding_id).device_id)
                    and str(device_map.get(binding_map.get(r.binding_id).device_id).platform or "").strip().lower() == "ios"
                )
                else "reddit"
            ),
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
    binding = db.query(NurtureBinding).filter(NurtureBinding.id == row.binding_id).first()
    if binding:
        active_plan = (
            db.query(NurturePlan)
            .filter(
                NurturePlan.binding_id == binding.id,
                NurturePlan.id != plan_id,
                NurturePlan.status.in_({"approved", "active"}),
            )
            .first()
        )
        if active_plan:
            raise HTTPException(
                status_code=409,
                detail=f"该设备已有执行中的计划(计划#{active_plan.id})，请先暂停或删除后再开始新计划",
            )
    now_utc = datetime.utcnow()
    now_cn = now_utc + timedelta(hours=8)

    old_items = (
        db.query(NurtureScheduleItem)
        .filter(NurtureScheduleItem.plan_id == plan_id, NurtureScheduleItem.status.in_(["scheduled", "dispatched", "running"]))
        .all()
    )
    for si in old_items:
        si.status = "cancelled"
        si.finished_at = now_utc
        db.add(si)

    # 重新计算 schedule：以「当前点击时间」作为整体时间轴的起点，
    # 按原计划中的相对结构生成时间，然后整体平移，使第一条任务尽快执行。
    schedule = []
    if isinstance(row.plan_json, dict):
        schedule = row.plan_json.get("schedule", [])

    items_with_time: list[tuple[dict[str, Any], datetime, int, int]] = []
    if schedule:
        # 以当天 00:00 为基准计算原始时间线（仅用于相对关系），之后整体平移到 now_utc 附近。
        base_day_utc = datetime(now_utc.year, now_utc.month, now_utc.day)
        for item in schedule:
            if not isinstance(item, dict):
                continue
            day_no = int(item.get("day_no") or 1)
            seq_no = int(item.get("seq_no") or 1)
            hour = int(item.get("hour") or 10)
            minute = int(item.get("minute") or 0)
            orig_when = base_day_utc + timedelta(days=max(day_no - 1, 0), hours=hour, minutes=minute)
            items_with_time.append((item, orig_when, day_no, seq_no))

    if items_with_time:
        # 找到原时间线上最早的一条，作为整体平移的参考点。
        first_when = min(x[1] for x in items_with_time)
        # 让第一条任务尽量「立即」执行，预留一个很小的缓冲。
        target_first = now_utc + timedelta(seconds=5)
        delta = target_first - first_when

        for item, orig_when, day_no, seq_no in items_with_time:
            new_when = orig_when + delta
            # 保护：避免因为计算误差导致时间落在当前时间之前。
            if new_when < now_utc:
                new_when = now_utc
            db.add(NurtureScheduleItem(
                user_id=current_user.id,
                binding_id=row.binding_id,
                plan_id=plan_id,
                day_no=day_no, seq_no=seq_no,
                stage=str(item.get("stage") or "warmup"),
                title=str(item.get("title") or f"nurture-day{day_no:02d}-s{seq_no}"),
                scheduled_at=new_when,
                status="scheduled",
                payload=item.get("payload") if isinstance(item.get("payload"), dict) else {},
            ))

    row.status = "approved"
    row.requires_reconfirm = False
    row.approved_by = current_user.id
    row.approved_at = now_utc
    # 使用平移后的首条任务时间作为计划 start_at，若无任务则退化为当前时间。
    if items_with_time:
        row.start_at = min(
            base_day_utc + timedelta(days=max(int(i.get("day_no") or 1) - 1, 0),
                                     hours=int(i.get("hour") or 10),
                                     minutes=int(i.get("minute") or 0))
            for i, _, _, _ in items_with_time
        ) + delta
    else:
        row.start_at = now_utc
    row.last_review_at = now_utc
    row.next_review_at = now_utc + timedelta(days=1)
    db.add(row)
    db.commit()
    dispatched = _dispatch_due_nurture_items(db)
    start_display = (row.start_at + timedelta(hours=8)).strftime("%Y-%m-%d") if row.start_at else now_cn.strftime("%Y-%m-%d")
    return {"detail": "approved", "plan_id": row.id, "dispatched_now": dispatched, "start_date": start_display}


class CopyPlanIn(BaseModel):
    target_device_ids: list[int]

@router.post("/nurture/plans/{plan_id}/copy", summary="复制计划到其他设备（用户态）")
def copy_nurture_plan(
    plan_id: int,
    payload: CopyPlanIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    src = db.query(NurturePlan).filter(NurturePlan.id == plan_id, NurturePlan.user_id == current_user.id).first()
    if not src:
        raise HTTPException(status_code=404, detail="plan not found")
    if not src.plan_json or not isinstance(src.plan_json, dict):
        raise HTTPException(status_code=400, detail="source plan has no valid plan_json")
    allowed = set(_allowed_device_ids_for_user(db, current_user))
    results: list[dict[str, Any]] = []
    for did in payload.target_device_ids:
        if did not in allowed:
            results.append({"device_id": did, "ok": False, "error": "no permission"})
            continue
        try:
            account_id = _resolve_device_account_id(db, current_user, did, None)
            binding = db.query(NurtureBinding).filter(
                NurtureBinding.user_id == current_user.id, NurtureBinding.device_id == did
            ).first()
            if not binding:
                binding = NurtureBinding(
                    user_id=current_user.id, device_id=did,
                    reddit_account_id=account_id, target_karma=100,
                    phase="warmup", automation_mode="normal", status="active",
                )
                db.add(binding)
                db.flush()
            plan_json = dict(src.plan_json)
            new_plan = NurturePlan(
                user_id=current_user.id, binding_id=binding.id,
                name=f"复制自#{plan_id} → 设备#{did}",
                status="draft",
                plan_version=src.plan_version or "v1",
                approval_mode=src.approval_mode or "plan_once_then_auto",
                plan_horizon_days=src.plan_horizon_days or 14,
                plan_json=plan_json,
                summary=f"[复制] {src.summary or ''}",
                objective=getattr(src, "objective", "") or "",
            )
            if hasattr(src, "eval_rounds") and src.eval_rounds:
                new_plan.eval_rounds = src.eval_rounds
            db.add(new_plan)
            db.flush()
            schedule = plan_json.get("schedule", [])
            for item in schedule:
                if not isinstance(item, dict):
                    continue
                day_no = int(item.get("day_no") or 1)
                seq_no = int(item.get("seq_no") or 1)
                db.add(NurtureScheduleItem(
                    user_id=current_user.id, binding_id=binding.id, plan_id=new_plan.id,
                    day_no=day_no, seq_no=seq_no,
                    stage=str(item.get("stage") or "warmup"),
                    title=str(item.get("title") or f"nurture-day{day_no:02d}-s{seq_no}"),
                    scheduled_at=datetime.utcnow(),
                    status="scheduled",
                    payload=item.get("payload") if isinstance(item.get("payload"), dict) else {},
                ))
            db.commit()
            results.append({"device_id": did, "ok": True, "plan_id": new_plan.id})
        except Exception as e:
            results.append({"device_id": did, "ok": False, "error": str(e)[:200]})
    ok_count = sum(1 for x in results if x["ok"])
    return {"detail": f"copied: {ok_count}/{len(results)}", "results": results}


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
    schedule_ids = [s.id for s in schedule_items]
    linked_task_ids = [s.control_task_id for s in schedule_items if s.control_task_id]
    if linked_task_ids:
        exec_ids = [e.id for e in db.query(TaskExecution).filter(TaskExecution.task_id.in_(linked_task_ids)).all()]
        if exec_ids:
            db.query(TaskExecutionLog).filter(TaskExecutionLog.execution_id.in_(exec_ids)).delete(synchronize_session=False)
            db.query(TaskExecution).filter(TaskExecution.id.in_(exec_ids)).delete(synchronize_session=False)
        db.query(ControlTask).filter(ControlTask.id.in_(linked_task_ids)).delete(synchronize_session=False)
    if schedule_ids:
        db.query(NurtureScheduleItem).filter(NurtureScheduleItem.id.in_(schedule_ids)).delete(synchronize_session=False)
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
    q = db.query(NurtureScheduleItem).filter(NurtureScheduleItem.user_id == current_user.id)
    if binding_id:
        q = q.filter(NurtureScheduleItem.binding_id == binding_id)
        latest_plan = (
            db.query(NurturePlan)
            .filter(NurturePlan.binding_id == binding_id, NurturePlan.user_id == current_user.id)
            .order_by(NurturePlan.id.desc())
            .first()
        )
        if latest_plan:
            q = q.filter(NurtureScheduleItem.plan_id == latest_plan.id)
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
    plans = (
        db.query(NurturePlan)
        .filter(NurturePlan.user_id == current_user.id)
        .order_by(NurturePlan.created_at.desc())
        .all()
    )
    if not plans:
        return []
    binding_ids = sorted({p.binding_id for p in plans})
    plan_ids = [p.id for p in plans]
    b_map: dict[int, NurtureBinding] = {}
    for b in db.query(NurtureBinding).filter(NurtureBinding.id.in_(binding_ids)).all():
        b_map[b.id] = b
    device_ids = sorted({b.device_id for b in b_map.values()})
    account_ids = sorted({b.reddit_account_id for b in b_map.values()})
    d_map: dict[int, MobileDevice] = {}
    a_map: dict[int, RedditAccountAsset] = {}
    if device_ids:
        for d in db.query(MobileDevice).filter(MobileDevice.id.in_(device_ids)).all():
            d_map[d.id] = d
    if account_ids:
        for a in db.query(RedditAccountAsset).filter(RedditAccountAsset.id.in_(account_ids)).all():
            a_map[a.id] = a
    agg: dict[int, dict[str, int]] = {pid: {"total": 0, "success": 0, "failed": 0, "running": 0, "scheduled": 0} for pid in plan_ids}
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
    for p in plans:
        b = b_map.get(p.binding_id)
        stat = agg.get(p.id, {"total": 0, "success": 0, "failed": 0, "running": 0, "scheduled": 0})
        dev = d_map.get(b.device_id) if b else None
        out.append(
            {
                "plan_id": p.id,
                "plan_name": p.name,
                "plan_status": p.status,
                "plan_horizon_days": getattr(p, "plan_horizon_days", 30),
                "plan_requires_reconfirm": bool(getattr(p, "requires_reconfirm", False)),
                "plan_summary": p.summary,
                "plan_objective": getattr(p, "objective", None) or "",
                "plan_source": (p.plan_json or {}).get("_source", "unknown") if isinstance(p.plan_json, dict) else "unknown",
                "plan_model": (p.plan_json or {}).get("_model", "") if isinstance(p.plan_json, dict) else "",
                "plan_gen_stage": (p.plan_json or {}).get("_stage", "") if isinstance(p.plan_json, dict) else "",
                "plan_gen_round": (p.plan_json or {}).get("_round", 0) if isinstance(p.plan_json, dict) else 0,
                "plan_eval_rounds": (p.plan_json or {}).get("_eval_rounds", []) if isinstance(p.plan_json, dict) else [],
                "plan_created_at": _iso(p.created_at),
                "plan_updated_at": _iso(p.updated_at),
                "binding_id": p.binding_id,
                "device_id": b.device_id if b else None,
                "device_label": _device_label_from_row(dev) if dev else None,
                "device_platform": dev.platform if dev else None,
                "task_platform": (
                    "reddit_ios"
                    if (dev and str(dev.platform or "").strip().lower() == "ios")
                    else "reddit"
                ),
                "reddit_account_id": b.reddit_account_id if b else None,
                "reddit_username": (a_map.get(b.reddit_account_id).username if b and a_map.get(b.reddit_account_id) else None),
                "phase": b.phase if b else None,
                "account_health": b.account_health if b else None,
                "current_karma": b.current_karma if b else 0,
                "target_karma": b.target_karma if b else 0,
                "metrics": stat,
                "created_at": _iso(p.created_at),
            }
        )
    return out


@router.get("/nurture/last-objective", summary="获取设备最近已执行计划的养号方向")
def get_last_objective(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bindings = db.query(NurtureBinding).filter(
        NurtureBinding.user_id == current_user.id,
        NurtureBinding.device_id == device_id,
    ).all()
    if not bindings:
        return {"objective": ""}
    binding_ids = [b.id for b in bindings]
    plan = (
        db.query(NurturePlan)
        .filter(
            NurturePlan.binding_id.in_(binding_ids),
            NurturePlan.status.in_(["active", "completed", "approved"]),
            NurturePlan.objective.isnot(None),
            NurturePlan.objective != "",
        )
        .order_by(NurturePlan.updated_at.desc())
        .first()
    )
    return {"objective": (plan.objective if plan else "") or ""}


@router.get("/nurture/models", summary="当前用户可用的养号模型列表")
def list_nurture_models(
    current_user: User = Depends(get_current_user),
):
    allowed = _allowed_models_for_user(current_user)
    return {
        "tier": _user_nurture_tier(current_user),
        "default_model": NURTURE_DEFAULT_MODEL,
        "models": allowed,
        "all_models": NURTURE_MODEL_OPTIONS if _is_admin(current_user) else None,
    }


class AdminSetNurtureTierIn(BaseModel):
    user_id: int
    tier: str = Field(max_length=32)


@router.post("/admin/set-nurture-tier", summary="管理员设置用户模型权限等级")
def admin_set_nurture_tier(
    payload: AdminSetNurtureTierIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="admin only")
    if payload.tier not in NURTURE_TIER_ORDER:
        raise HTTPException(status_code=400, detail=f"invalid tier, allowed: {list(NURTURE_TIER_ORDER.keys())}")
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    user.nurture_model_tier = payload.tier
    db.add(user)
    db.commit()
    return {"user_id": user.id, "nurture_model_tier": payload.tier}


@router.get("/admin/users", summary="管理员查看用户列表")
def list_users_for_admin(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="admin only")
    rows = db.query(User).order_by(User.id.asc()).all()
    return [{"id": u.id, "email": u.email, "role": getattr(u, "role", "user"), "nurture_model_tier": getattr(u, "nurture_model_tier", "basic") or "basic"} for u in rows]


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

        # 自动根据设备平台选择任务平台：
        # - 当 payload.platform 显式指定时尊重前端传入
        # - 未指定时：android 设备 -> reddit，ios 设备 -> reddit_ios
        task_platform = (payload.platform or "reddit").strip() or "reddit"
        if not (payload.platform and payload.platform.strip()) and dev_id is not None:
            dev = db.query(MobileDevice).filter(MobileDevice.id == dev_id).first()
            if dev:
                plat = (dev.platform or "android").strip().lower()
                if plat == "ios":
                    task_platform = "reddit_ios"

        return ControlTask(
            user_id=current_user.id,
            title=payload.title.strip(),
            platform=task_platform,
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


# ────────────────────────────────────────────
# 统计 / 每日报告 / 政策爬取 / 执行列表
# ────────────────────────────────────────────

def _parse_date_param(value: Optional[str]) -> Optional[date]:
    """Parse YYYY-MM-DD date param safely."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


def _collect_daily_stats(
    db: Session,
    start_utc: Optional[datetime] = None,
    end_utc: Optional[datetime] = None,
) -> dict[str, Any]:
    # 默认统计最近 24 小时；如提供 start/end，则使用 [start, end] 间的数据。
    now = datetime.utcnow()
    if end_utc is None:
        end_utc = now
    if start_utc is None:
        start_utc = end_utc - timedelta(hours=24)

    items = (
        db.query(NurtureScheduleItem)
        .filter(
            NurtureScheduleItem.dispatched_at.isnot(None),
            NurtureScheduleItem.dispatched_at >= start_utc,
            NurtureScheduleItem.dispatched_at < end_utc,
        )
        .all()
    )
    total = len(items)
    success = sum(1 for i in items if i.status == "success")
    failed = sum(1 for i in items if i.status == "failed")
    running = sum(1 for i in items if i.status in ("running", "dispatched"))
    skipped = sum(1 for i in items if i.status == "skipped")
    scheduled = sum(1 for i in items if i.status == "scheduled")

    by_action: dict[str, dict[str, int]] = {}
    for i in items:
        act = (i.payload or {}).get("action", "unknown") if isinstance(i.payload, dict) else "unknown"
        if act not in by_action:
            by_action[act] = {"total": 0, "success": 0, "failed": 0}
        by_action[act]["total"] += 1
        if i.status == "success":
            by_action[act]["success"] += 1
        elif i.status == "failed":
            by_action[act]["failed"] += 1

    bindings = {i.binding_id for i in items}
    b_rows = db.query(NurtureBinding).filter(NurtureBinding.id.in_(bindings)).all() if bindings else []
    b_map = {b.id: b for b in b_rows}
    d_ids = {b.device_id for b in b_rows}
    d_rows = db.query(MobileDevice).filter(MobileDevice.id.in_(d_ids)).all() if d_ids else []
    d_map = {d.id: d for d in d_rows}

    by_device: dict[int, dict[str, Any]] = {}
    for i in items:
        b = b_map.get(i.binding_id)
        did = b.device_id if b else 0
        if did not in by_device:
            dev = d_map.get(did)
            by_device[did] = {"device_id": did, "device_label": _device_label_from_row(dev) if dev else f"#{did}", "total": 0, "success": 0, "failed": 0}
        by_device[did]["total"] += 1
        if i.status == "success":
            by_device[did]["success"] += 1
        elif i.status == "failed":
            by_device[did]["failed"] += 1

    return {
        "period": "24h",
        "total": total, "success": success, "failed": failed,
        "running": running, "scheduled": scheduled, "skipped": skipped,
        "success_rate": round(success / total, 3) if total else 0,
        "by_action": by_action,
        "by_device": sorted(by_device.values(), key=lambda x: x["total"], reverse=True),
    }


@router.get("/stats/daily", summary="任务统计（可选时间区间）")
def get_daily_stats(
    start: Optional[str] = Query(default=None, description="统计起始日期 YYYY-MM-DD"),
    end: Optional[str] = Query(default=None, description="统计结束日期 YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_date = _parse_date_param(start)
    end_date = _parse_date_param(end)

    if start and not start_date:
        raise HTTPException(status_code=400, detail="invalid start date")
    if end and not end_date:
        raise HTTPException(status_code=400, detail="invalid end date")

    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start date must be <= end date")

    # 限制最大区间长度，避免一次性拉取过多历史数据。
    max_days = 7
    if start_date and end_date and (end_date - start_date).days > max_days:
        raise HTTPException(status_code=400, detail=f"date range too large, max {max_days} days")

    # 只填了一个日期时，按单日区间处理。
    if start_date and not end_date:
        end_date = start_date
    if end_date and not start_date:
        start_date = end_date

    start_utc: Optional[datetime] = None
    end_utc: Optional[datetime] = None
    if start_date and end_date:
        # [start_date 00:00, end_date 次日 00:00)
        start_utc = datetime(start_date.year, start_date.month, start_date.day)
        end_utc = datetime(end_date.year, end_date.month, end_date.day) + timedelta(days=1)

    return _collect_daily_stats(db, start_utc=start_utc, end_utc=end_utc)


_REDDIT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"


def _html_to_text(html: str, max_len: int = 8000) -> str:
    import re as _re
    clean = _re.sub(r"<script[\s\S]*?</script>", " ", html, flags=_re.I)
    clean = _re.sub(r"<style[\s\S]*?</style>", " ", clean, flags=_re.I)
    clean = _re.sub(r"<[^>]+>", " ", clean)
    clean = _re.sub(r"\s+", " ", clean).strip()
    return clean[:max_len]


def _fetch_url_text(url: str, max_len: int = 8000) -> Optional[str]:
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": _REDDIT_UA})
            if resp.status_code < 300 and resp.text:
                return _html_to_text(resp.text, max_len)
    except Exception as exc:
        logger.warning("fetch failed for %s: %s", url, exc)
    return None


def _fetch_reddit_json(url: str) -> Optional[Any]:
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": _REDDIT_UA})
            if resp.status_code < 300:
                return resp.json()
    except Exception as exc:
        logger.warning("reddit json fetch failed for %s: %s", url, exc)
    return None


def _crawl_reddit_policy() -> Optional[dict[str, Any]]:
    """Crawl official Reddit policy pages."""
    urls = [
        "https://www.redditinc.com/policies/content-policy",
        "https://support.reddit.com/hc/en-us/articles/20451297193108",
    ]
    texts: list[str] = []
    fetched_urls: list[str] = []
    for url in urls:
        t = _fetch_url_text(url)
        if t:
            texts.append(t)
            fetched_urls.append(url)
    if not texts:
        return None
    return {"source_urls": fetched_urls, "raw_texts": texts}


def _crawl_reddit_announcements() -> list[dict[str, str]]:
    """Fetch recent posts from official Reddit announcement subreddits."""
    subs = ["reddit", "changelog", "ModSupport"]
    posts: list[dict[str, str]] = []
    for sub in subs:
        data = _fetch_reddit_json(f"https://www.reddit.com/r/{sub}/new.json?limit=5")
        if not data:
            continue
        for child in (data.get("data", {}).get("children", []))[:5]:
            p = child.get("data", {})
            title = p.get("title", "")
            selftext = (p.get("selftext") or "")[:800]
            created = p.get("created_utc", 0)
            if title:
                posts.append({
                    "subreddit": sub,
                    "title": title,
                    "text": selftext,
                    "url": f"https://www.reddit.com{p.get('permalink', '')}",
                    "created_utc": str(int(created)) if created else "",
                })
    return posts


def _crawl_subreddit_rules(db: Session) -> list[dict[str, Any]]:
    """Fetch rules for subreddits referenced in active nurture plans."""
    active_plans = db.query(NurturePlan).filter(NurturePlan.status.in_(["approved", "active"])).all()
    subreddit_names: set[str] = set()
    for p in active_plans:
        pj = p.plan_json if isinstance(p.plan_json, dict) else {}
        for item in pj.get("schedule", []):
            payload = item.get("payload", {})
            sub = payload.get("subreddit_name", "")
            if sub:
                subreddit_names.add(sub)

    rules_data: list[dict[str, Any]] = []
    for sub_name in list(subreddit_names)[:10]:
        data = _fetch_reddit_json(f"https://www.reddit.com/r/{sub_name}/about/rules.json")
        if not data:
            continue
        rules_list = data.get("rules", data) if isinstance(data, dict) else data
        if isinstance(rules_list, list):
            rules_data.append({
                "subreddit": sub_name,
                "rules": [
                    {"title": r.get("short_name", ""), "description": (r.get("description", "") or "")[:300]}
                    for r in rules_list[:15]
                ],
            })
        elif isinstance(rules_list, dict) and "rules" in rules_list:
            inner = rules_list["rules"]
            if isinstance(inner, list):
                rules_data.append({
                    "subreddit": sub_name,
                    "rules": [
                        {"title": r.get("short_name", ""), "description": (r.get("description", "") or "")[:300]}
                        for r in inner[:15]
                    ],
                })
    return rules_data


def _collect_execution_anomalies(db: Session, days: int = 2) -> dict[str, Any]:
    """Analyze recent execution logs for anomaly patterns."""
    since = datetime.utcnow() - timedelta(days=days)
    failed_items = (
        db.query(NurtureScheduleItem)
        .filter(
            NurtureScheduleItem.status.in_(["failed", "skipped"]),
            NurtureScheduleItem.updated_at >= since,
        )
        .order_by(NurtureScheduleItem.updated_at.desc())
        .limit(100)
        .all()
    )
    error_counts: dict[str, int] = {}
    error_samples: list[dict[str, str]] = []
    for si in failed_items:
        err = si.last_error_message or si.last_error_code or "unknown"
        err_key = err[:80]
        error_counts[err_key] = error_counts.get(err_key, 0) + 1
        if len(error_samples) < 15:
            error_samples.append({
                "plan_id": str(si.plan_id),
                "day_seq": f"{si.day_no}-{si.seq_no}",
                "status": si.status,
                "error": err[:200],
            })

    exec_logs = (
        db.query(TaskExecutionLog)
        .filter(TaskExecutionLog.created_at >= since, TaskExecutionLog.level.in_(["error", "warning"]))
        .order_by(TaskExecutionLog.created_at.desc())
        .limit(50)
        .all()
    )
    log_patterns: dict[str, int] = {}
    for log in exec_logs:
        msg = (log.message or "")[:100].lower()
        for keyword in ["rate limit", "captcha", "banned", "suspended", "shadow", "locked", "spam", "timeout", "403", "429"]:
            if keyword in msg:
                log_patterns[keyword] = log_patterns.get(keyword, 0) + 1

    return {
        "failed_count": len(failed_items),
        "error_distribution": dict(sorted(error_counts.items(), key=lambda x: -x[1])[:10]),
        "risk_signals": log_patterns,
        "error_samples": error_samples,
    }


def _gather_all_intelligence(db: Session) -> dict[str, Any]:
    """Gather all intelligence sources into a single dict."""
    intel: dict[str, Any] = {"sources_used": []}

    policy = _crawl_reddit_policy()
    if policy:
        intel["official_policy"] = policy
        intel["sources_used"].append("official_policy_pages")

    announcements = _crawl_reddit_announcements()
    if announcements:
        intel["announcements"] = announcements
        intel["sources_used"].append(f"reddit_announcements({len(announcements)} posts)")

    sub_rules = _crawl_subreddit_rules(db)
    if sub_rules:
        intel["subreddit_rules"] = sub_rules
        intel["sources_used"].append(f"subreddit_rules({len(sub_rules)} subs)")

    anomalies = _collect_execution_anomalies(db)
    if anomalies["failed_count"] > 0 or anomalies["risk_signals"]:
        intel["execution_anomalies"] = anomalies
        intel["sources_used"].append("execution_anomalies")

    return intel


def _summarize_policy_with_ai(intel: dict[str, Any], prev_summary: str = "", model: str = "") -> Optional[dict]:
    use_model = model.strip() if model else (settings.nurture_llm_model or "deepseek-chat")

    prompt_parts = ["你是 Reddit 平台政策与风控综合分析师。根据以下多维度情报，输出严格 JSON 格式的综合分析。\n"]

    if "official_policy" in intel:
        combined = "\n---\n".join(intel["official_policy"]["raw_texts"])[:6000]
        prompt_parts.append(f"=== 1. Reddit 官方政策页面 ===\n{combined}\n")

    if "announcements" in intel:
        ann_text = "\n".join(
            f"[r/{a['subreddit']}] {a['title']}: {a['text'][:200]}"
            for a in intel["announcements"][:8]
        )[:3000]
        prompt_parts.append(f"=== 2. Reddit 官方公告（近期） ===\n{ann_text}\n")

    if "subreddit_rules" in intel:
        rules_text = ""
        for sr in intel["subreddit_rules"][:5]:
            rules_text += f"\nr/{sr['subreddit']}:\n"
            for r in sr["rules"][:8]:
                rules_text += f"  - {r['title']}: {r['description'][:100]}\n"
        prompt_parts.append(f"=== 3. 目标子版块规则 ===\n{rules_text[:3000]}\n")

    if "execution_anomalies" in intel:
        anom = intel["execution_anomalies"]
        anom_text = f"近2天失败任务: {anom['failed_count']}个\n"
        if anom["risk_signals"]:
            anom_text += f"风险信号: {json.dumps(anom['risk_signals'], ensure_ascii=False)}\n"
        if anom["error_distribution"]:
            top_errs = list(anom["error_distribution"].items())[:5]
            anom_text += "常见错误:\n" + "\n".join(f"  [{cnt}次] {err}" for err, cnt in top_errs) + "\n"
        prompt_parts.append(f"=== 4. 内部执行异常监测 ===\n{anom_text}\n")

    if prev_summary:
        prompt_parts.append(f"=== 上次分析摘要 ===\n{prev_summary}\n请与上次对比，识别变化。\n")

    prompt_parts.append(
        "=== 输出格式（严格 JSON） ===\n"
        "{\n"
        '  "ai_summary": "<中文综合摘要，涵盖政策现状+公告动态+子版块规则要点+异常信号，300字内>",\n'
        '  "key_changes": ["变化或发现1", "变化或发现2", ...],\n'
        '  "subreddit_risks": [{"sub":"子版块名","risk":"具体风险描述"}],\n'
        '  "anomaly_assessment": "<中文，基于执行数据的风险评估，100字内>",\n'
        '  "severity": "low/medium/high"\n'
        "}\n"
        "如果没有明显变化或风险，severity 设为 low。"
    )

    prompt = "\n".join(prompt_parts)
    if len(prompt) > 15000:
        prompt = prompt[:15000] + "\n...(截断)"

    result = _call_llm_with_fallback(
        model=use_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        timeout_read=120.0,
    )
    if not result["ok"]:
        logger.warning("policy AI summary all channels failed: %s", result["error"])
        return None
    try:
        content = _extract_llm_content(result["data"])
        return _parse_json_from_llm(content)
    except Exception as exc:
        logger.warning("policy AI summary parse failed: %s", exc)
        return None


def _ensure_daily_policy(db: Session, model: str = "") -> Optional[RedditPolicySnapshot]:
    today = datetime.utcnow().date()
    existing = (
        db.query(RedditPolicySnapshot)
        .filter(func.date(RedditPolicySnapshot.crawled_at) == today)
        .order_by(RedditPolicySnapshot.id.desc())
        .first()
    )
    if existing:
        return existing
    intel = _gather_all_intelligence(db)
    if not intel.get("official_policy") and not intel.get("announcements"):
        return None
    prev = db.query(RedditPolicySnapshot).order_by(RedditPolicySnapshot.id.desc()).first()
    prev_summary = prev.ai_summary if prev else ""
    ai_result = _summarize_policy_with_ai(intel, prev_summary, model=model)
    all_sources = ", ".join(intel.get("sources_used", []))
    raw_parts: list[str] = []
    if "official_policy" in intel:
        raw_parts.extend(intel["official_policy"]["raw_texts"])
    if "announcements" in intel:
        raw_parts.append("--- ANNOUNCEMENTS ---\n" + json.dumps(intel["announcements"], ensure_ascii=False)[:4000])
    if "subreddit_rules" in intel:
        raw_parts.append("--- SUBREDDIT RULES ---\n" + json.dumps(intel["subreddit_rules"], ensure_ascii=False)[:4000])
    if "execution_anomalies" in intel:
        raw_parts.append("--- ANOMALIES ---\n" + json.dumps(intel["execution_anomalies"], ensure_ascii=False)[:2000])
    snap = RedditPolicySnapshot(
        source_url=all_sources,
        raw_content="\n---\n".join(raw_parts)[:20000],
        ai_summary=ai_result.get("ai_summary", "") if ai_result else "数据采集成功但 AI 摘要失败",
        key_changes=ai_result.get("key_changes", []) if ai_result else [],
        severity=ai_result.get("severity", "low") if ai_result else "unknown",
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return snap


@router.get("/stats/policy-latest", summary="最新 Reddit 政策快照")
def get_policy_latest(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    snap = db.query(RedditPolicySnapshot).order_by(RedditPolicySnapshot.id.desc()).first()
    if not snap:
        return {"exists": False}
    return {
        "exists": True,
        "id": snap.id,
        "crawled_at": snap.crawled_at.isoformat() if snap.crawled_at else "",
        "ai_summary": snap.ai_summary or "",
        "key_changes": snap.key_changes or [],
        "severity": snap.severity,
        "sources": snap.source_url or "",
    }


@router.post("/stats/policy-refresh", summary="手动刷新 Reddit 政策")
def refresh_policy(
    model: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    intel = _gather_all_intelligence(db)
    if not intel.get("official_policy") and not intel.get("announcements"):
        raise HTTPException(status_code=502, detail="无法抓取任何 Reddit 数据源")
    prev = db.query(RedditPolicySnapshot).order_by(RedditPolicySnapshot.id.desc()).first()
    ai_result = _summarize_policy_with_ai(intel, prev.ai_summary if prev else "", model=model)
    all_sources = ", ".join(intel.get("sources_used", []))
    raw_parts: list[str] = []
    if "official_policy" in intel:
        raw_parts.extend(intel["official_policy"]["raw_texts"])
    if "announcements" in intel:
        raw_parts.append("--- ANNOUNCEMENTS ---\n" + json.dumps(intel["announcements"], ensure_ascii=False)[:4000])
    if "subreddit_rules" in intel:
        raw_parts.append("--- SUBREDDIT RULES ---\n" + json.dumps(intel["subreddit_rules"], ensure_ascii=False)[:4000])
    if "execution_anomalies" in intel:
        raw_parts.append("--- ANOMALIES ---\n" + json.dumps(intel["execution_anomalies"], ensure_ascii=False)[:2000])
    snap = RedditPolicySnapshot(
        source_url=all_sources,
        raw_content="\n---\n".join(raw_parts)[:20000],
        ai_summary=ai_result.get("ai_summary", "") if ai_result else "AI 摘要失败",
        key_changes=ai_result.get("key_changes", []) if ai_result else [],
        severity=ai_result.get("severity", "low") if ai_result else "unknown",
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return {
        "id": snap.id, "ai_summary": snap.ai_summary, "severity": snap.severity,
        "sources": intel.get("sources_used", []),
    }


def _generate_daily_report_data(db: Session, model: str = "") -> dict[str, Any]:
    stats = _collect_daily_stats(db)
    policy = _ensure_daily_policy(db, model=model)
    anomalies = _collect_execution_anomalies(db)

    active_plans = db.query(NurturePlan).filter(NurturePlan.status.in_(["approved", "active"])).all()
    binding_ids = [p.binding_id for p in active_plans]
    bindings = db.query(NurtureBinding).filter(NurtureBinding.id.in_(binding_ids)).all() if binding_ids else []
    d_ids = {b.device_id for b in bindings}
    devices = db.query(MobileDevice).filter(MobileDevice.id.in_(d_ids)).all() if d_ids else []
    d_map = {d.id: d for d in devices}

    account_context = []
    for b in bindings:
        dev = d_map.get(b.device_id)
        account_context.append({
            "device": _device_label_from_row(dev) if dev else f"#{b.device_id}",
            "phase": b.phase, "karma": b.current_karma, "target_karma": b.target_karma,
            "health": b.account_health,
        })

    use_model = model.strip() if model else (settings.nurture_llm_model or "deepseek-chat")
    if not _get_llm_endpoints():
        return {"overall_score": 0, "execution_analysis": "LLM 未配置", "policy_analysis": "", "recommendations": [], "severity": "unknown", "raw_stats": stats}

    anomaly_section = ""
    if anomalies["failed_count"] > 0 or anomalies["risk_signals"]:
        anomaly_section = f"\n=== 执行异常监测 ===\n近2天失败任务: {anomalies['failed_count']}个\n"
        if anomalies["risk_signals"]:
            anomaly_section += f"风险信号(关键词命中): {json.dumps(anomalies['risk_signals'], ensure_ascii=False)}\n"
        if anomalies["error_distribution"]:
            top3 = list(anomalies["error_distribution"].items())[:3]
            anomaly_section += "高频错误: " + "; ".join(f"{e}({c}次)" for e, c in top3) + "\n"

    prompt = (
        "你是 Reddit 养号运营分析师。根据以下多维度数据生成每日运营报告，输出严格 JSON。\n\n"
        f"=== 昨日执行统计 ===\n{json.dumps(stats, ensure_ascii=False)}\n\n"
        f"=== 当前活跃账号状态 ===\n{json.dumps(account_context, ensure_ascii=False)}\n\n"
        f"=== Reddit 平台政策综合分析 ===\n{policy.ai_summary if policy else '暂无政策数据'}\n"
        f"政策变化: {json.dumps(policy.key_changes if policy else [], ensure_ascii=False)}\n"
        f"风险等级: {policy.severity if policy else 'unknown'}\n"
        f"{anomaly_section}\n"
        "=== 输出格式 ===\n"
        "{\n"
        '  "overall_score": <0-100 综合评分>,\n'
        '  "execution_analysis": "<中文，昨日执行情况分析，200字内>",\n'
        '  "policy_analysis": "<中文，平台政策+子版块规则+异常信号综合风险分析，200字内>",\n'
        '  "recommendations": ["建议1", "建议2", ...],\n'
        '  "severity": "low/medium/high"\n'
        "}\n"
        "overall_score 综合考虑成功率、账号健康度、政策风险、异常信号。"
    )
    llm_result = _call_llm_with_fallback(
        model=use_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.15,
        timeout_read=180.0,
    )
    if not llm_result["ok"]:
        return {"overall_score": 0, "execution_analysis": f"所有 LLM 通道失败: {llm_result['error']}", "policy_analysis": "", "recommendations": [], "severity": "unknown", "raw_stats": stats}
    try:
        content = _extract_llm_content(llm_result["data"])
        result = _parse_json_from_llm(content)
        result["raw_stats"] = stats
        return result
    except Exception as exc:
        logger.warning("daily report AI parse failed: %s", exc)
        return {"overall_score": 0, "execution_analysis": f"AI 输出解析失败: {exc}", "policy_analysis": "", "recommendations": [], "severity": "unknown", "raw_stats": stats}


@router.get("/stats/report", summary="最新每日综合报告")
def get_daily_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = datetime.utcnow().date()
    report = db.query(DailyReport).filter(DailyReport.report_date == today).first()
    if not report:
        yesterday = today - timedelta(days=1)
        report = db.query(DailyReport).filter(DailyReport.report_date == yesterday).first()
    if not report:
        return {"exists": False}
    return {
        "exists": True,
        "id": report.id,
        "report_date": report.report_date.isoformat(),
        "overall_score": report.overall_score,
        "execution_analysis": report.execution_analysis or "",
        "policy_analysis": report.policy_analysis or "",
        "recommendations": report.recommendations or [],
        "severity": report.severity,
        "raw_stats": report.raw_stats,
        "created_at": report.created_at.isoformat() if report.created_at else "",
    }


@router.post("/stats/report-refresh", summary="手动生成/刷新每日报告")
def refresh_daily_report(
    model: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = _generate_daily_report_data(db, model=model)
    today = datetime.utcnow().date()
    report = db.query(DailyReport).filter(DailyReport.report_date == today).first()
    if report:
        report.overall_score = int(data.get("overall_score", 0))
        report.execution_analysis = data.get("execution_analysis", "")
        report.policy_analysis = data.get("policy_analysis", "")
        report.recommendations = data.get("recommendations", [])
        report.severity = data.get("severity", "low")
        report.raw_stats = data.get("raw_stats")
    else:
        report = DailyReport(
            report_date=today,
            overall_score=int(data.get("overall_score", 0)),
            execution_analysis=data.get("execution_analysis", ""),
            policy_analysis=data.get("policy_analysis", ""),
            recommendations=data.get("recommendations", []),
            severity=data.get("severity", "low"),
            raw_stats=data.get("raw_stats"),
        )
        db.add(report)
    db.commit()
    db.refresh(report)
    return {
        "id": report.id, "report_date": report.report_date.isoformat(),
        "overall_score": report.overall_score, "severity": report.severity,
    }


@router.get("/nurture/running", summary="养号计划执行列表（含历史）")
def get_nurture_running(
    status: Optional[str] = Query(default=None, description="筛选计划状态: all/active/approved/paused/completed，默认显示 approved+active+paused"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed = {"approved", "active", "paused", "completed"}
    if status and status != "all":
        filter_statuses = [s.strip() for s in status.split(",") if s.strip() in allowed]
    elif status == "all":
        filter_statuses = list(allowed)
    else:
        filter_statuses = ["approved", "active", "paused"]
    plans = (
        db.query(NurturePlan)
        .filter(NurturePlan.user_id == current_user.id, NurturePlan.status.in_(filter_statuses))
        .order_by(NurturePlan.updated_at.desc())
        .all()
    )
    if not plans:
        return []
    plan_ids = [p.id for p in plans]
    binding_ids = [p.binding_id for p in plans]

    items = (
        db.query(NurtureScheduleItem)
        .filter(NurtureScheduleItem.plan_id.in_(plan_ids))
        .order_by(NurtureScheduleItem.day_no.asc(), NurtureScheduleItem.seq_no.asc())
        .all()
    )

    bindings = db.query(NurtureBinding).filter(NurtureBinding.id.in_(binding_ids)).all()
    b_map = {b.id: b for b in bindings}
    d_ids = {b.device_id for b in bindings}
    d_rows = db.query(MobileDevice).filter(MobileDevice.id.in_(d_ids)).all() if d_ids else []
    d_map = {d.id: d for d in d_rows}

    items_by_plan: dict[int, list] = {}
    for i in items:
        items_by_plan.setdefault(i.plan_id, []).append(i)

    def _serialize_item(si):
        return {
            "id": si.id, "day_no": si.day_no, "seq_no": si.seq_no,
            "action": (si.payload or {}).get("action", "?") if isinstance(si.payload, dict) else "?",
            "title": si.title, "status": si.status, "stage": si.stage,
            "scheduled_at": si.scheduled_at.isoformat() if si.scheduled_at else "",
            "started_at": si.started_at.isoformat() if si.started_at else "",
            "finished_at": si.finished_at.isoformat() if si.finished_at else "",
            "error": si.last_error_message or "",
        }

    out = []
    for p in plans:
        b = b_map.get(p.binding_id)
        dev = d_map.get(b.device_id) if b else None
        p_items = items_by_plan.get(p.id, [])
        if not p_items:
            out.append({
                "plan_id": p.id, "plan_name": p.name, "plan_status": p.status,
                "device_label": _device_label_from_row(dev) if dev else None,
                "device_id": b.device_id if b else None,
                "objective": getattr(p, "objective", "") or "",
                "round": 1, "items": [],
            })
            continue
        rounds: dict[str, list] = {}
        for si in p_items:
            key = si.created_at.strftime("%Y%m%d%H%M%S") if si.created_at else "0"
            rounds.setdefault(key, []).append(si)
        sorted_keys = sorted(rounds.keys(), reverse=True)
        for idx, key in enumerate(sorted_keys):
            round_items = rounds[key]
            is_current = (idx == 0)
            all_cancelled = all(si.status == "cancelled" for si in round_items)
            round_status = p.status if is_current else ("cancelled" if all_cancelled else "历史")
            out.append({
                "plan_id": p.id, "plan_name": p.name, "plan_status": round_status,
                "device_label": _device_label_from_row(dev) if dev else None,
                "device_id": b.device_id if b else None,
                "objective": getattr(p, "objective", "") or "",
                "round": len(sorted_keys) - idx,
                "round_total": len(sorted_keys),
                "is_current_round": is_current,
                "items": [_serialize_item(si) for si in round_items],
            })
    return out

