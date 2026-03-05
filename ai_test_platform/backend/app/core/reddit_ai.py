"""
Reddit 群控 AI 服务：风控分析与策略生成。
- analyze_risk: 基于执行日志做风控分析，调用 LLM，写入 RiskAnalysisReport
- generate_strategy: 生成养号/发帖策略，调用 LLM，写入 RedditStrategyConfig
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models import (
    RiskAnalysisReport,
    RedditStrategyConfig,
    TaskExecution,
    TaskExecutionLog,
)
from .llm_client import call_llm, is_llm_enabled

# 默认使用轻量模型以控制成本
DEFAULT_MODEL_ID = "volc:doubao-flash"


def analyze_risk(
    db: Session,
    user_id: int,
    platform: str = "reddit",
    days: int = 7,
) -> RiskAnalysisReport:
    """
    基于近 N 天执行日志做风控分析，调用 LLM 生成报告并写入 RiskAnalysisReport。
    """
    since = datetime.utcnow() - timedelta(days=days)
    logs = (
        db.query(TaskExecutionLog, TaskExecution)
        .join(TaskExecution, TaskExecution.id == TaskExecutionLog.execution_id)
        .filter(
            TaskExecution.user_id == user_id,
            TaskExecution.started_at >= since,
        )
        .order_by(TaskExecutionLog.created_at.asc())
        .limit(500)
        .all()
    )
    exec_summary: list[dict[str, Any]] = []
    for log_row, exe_row in logs:
        exec_summary.append({
            "execution_id": exe_row.id,
            "task_id": exe_row.task_id,
            "status": exe_row.status,
            "step": exe_row.step,
            "error_code": exe_row.error_code,
            "error_message": exe_row.error_message,
            "level": log_row.level,
            "message": log_row.message[:500] if log_row.message else "",
            "created_at": log_row.created_at.isoformat() if log_row.created_at else "",
        })
    if not exec_summary:
        report = RiskAnalysisReport(
            user_id=user_id,
            platform=platform,
            summary="近 {} 天无执行日志，无法进行风控分析。".format(days),
            findings=None,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    if not is_llm_enabled():
        report = RiskAnalysisReport(
            user_id=user_id,
            platform=platform,
            summary="LLM 未配置，无法进行 AI 风控分析。请配置 OPENAI_API_KEY。",
            findings={"raw_logs_count": len(exec_summary)},
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    user_prompt = (
        "以下为 Reddit 群控近 {} 天的执行日志摘要（JSON 格式）。\n"
        "请分析其中可能存在的风控风险，包括但不限于：\n"
        "- 账号异常（封禁、限流、验证码）\n"
        "- 操作频率过高或行为模式异常\n"
        "- 内容违规或敏感词触发\n"
        "- 设备/IP 相关风险\n"
        "请用中文输出：1) 总体风险摘要（2-3 段）；2) 具体发现列表（findings 数组，每项含 risk_type、description、severity、suggestion）。\n\n"
        "执行日志：\n{}"
    ).format(days, str(exec_summary)[:8000])

    system_prompt = (
        "你是 Reddit 群控风控分析专家。根据执行日志识别潜在风险，给出简洁、可操作的建议。"
        "输出格式：先写「总体摘要」段落，再输出 JSON 格式的 findings 数组。"
    )
    try:
        resp = call_llm(
            model_id=DEFAULT_MODEL_ID,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=2048,
        )
        content = (resp.get("content") or "").strip()
        findings = None
        if "findings" in content.lower() or "[" in content:
            import json
            import re
            try:
                json_match = re.search(r"\[[\s\S]*\]", content)
                if json_match:
                    findings = json.loads(json_match.group())
            except Exception:
                pass
        report = RiskAnalysisReport(
            user_id=user_id,
            platform=platform,
            summary=content[:8000] if content else "分析完成，无结构化输出。",
            findings=findings,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report
    except Exception as e:
        report = RiskAnalysisReport(
            user_id=user_id,
            platform=platform,
            summary="风控分析失败：{}".format(str(e)),
            findings={"error": str(e)},
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report


def generate_strategy(
    db: Session,
    user_id: int,
    category: str = "general",
    niche: str = "general",
    name: Optional[str] = None,
) -> RedditStrategyConfig:
    """
    生成养号/发帖策略，调用 LLM，写入 RedditStrategyConfig。
    """
    if not is_llm_enabled():
        cfg = RedditStrategyConfig(
            user_id=user_id,
            name=name or "默认策略",
            category=category,
            config={
                "nurture_phases": [],
                "post_templates": [],
                "target_subs": [],
                "note": "LLM 未配置，请配置 OPENAI_API_KEY 后重新生成。",
            },
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
        return cfg

    user_prompt = (
        "请为 Reddit 群控生成一套养号与发帖策略。\n"
        "- 品类（category）：{}\n"
        "- 细分领域（niche）：{}\n\n"
        "请输出 JSON 格式的 config，包含：\n"
        "- nurture_phases: 养号阶段列表，每项含 phase_name、duration_days、daily_actions（浏览/点赞/评论等）\n"
        "- post_templates: 发帖模板列表，每项含 title_template、content_template、subreddit_hint\n"
        "- target_subs: 目标子版块列表\n"
        "- 其他你认为有用的字段\n\n"
        "只输出 JSON，不要其他说明。"
    ).format(category, niche)

    system_prompt = (
        "你是 Reddit 运营专家。根据品类和细分领域，生成可执行的养号与发帖策略。"
        "输出必须是合法 JSON 对象，键为 nurture_phases、post_templates、target_subs 等。"
    )
    try:
        resp = call_llm(
            model_id=DEFAULT_MODEL_ID,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.5,
            max_tokens=2048,
        )
        content = (resp.get("content") or "").strip()
        import json
        import re
        config: dict = {
            "nurture_phases": [],
            "post_templates": [],
            "target_subs": [],
            "note": "解析失败时使用默认结构",
        }
        try:
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                parsed = json.loads(json_match.group())
                if isinstance(parsed, dict):
                    config = parsed
        except Exception:
            config["note"] = "JSON 解析失败: " + content[:200]
        cfg = RedditStrategyConfig(
            user_id=user_id,
            name=name or "{} - {} 策略".format(category, niche),
            category=category,
            config=config,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
        return cfg
    except Exception as e:
        cfg = RedditStrategyConfig(
            user_id=user_id,
            name=name or "{} - {} 策略".format(category, niche),
            category=category,
            config={
                "nurture_phases": [],
                "post_templates": [],
                "target_subs": [],
                "note": "生成失败: {}".format(str(e)),
            },
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
        return cfg
