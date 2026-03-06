"""Reddit action catalog -- the single source of truth for what
the local agent can execute and what the cloud AI should reference
when orchestrating nurture plans."""

from __future__ import annotations

from typing import Any, Callable

ACTION_CATALOG: list[dict[str, Any]] = [
    {
        "action": "browse",
        "description": "Scroll through the Reddit home / popular feed, randomly pause to read posts.",
        "description_zh": "滑动浏览首页/热门 Feed，随机停留阅读帖子",
        "required_params": [],
        "optional_params": ["duration_min", "max_scrolls"],
        "defaults": {"duration_min": 8, "max_scrolls": 30},
        "stages": ["warmup", "steady", "engage", "post_ready"],
        "risk_level": "low",
    },
    {
        "action": "search",
        "description": "Tap the search bar, type a keyword, browse the search results.",
        "description_zh": "点击搜索栏，输入关键词，浏览搜索结果",
        "required_params": ["keyword"],
        "optional_params": ["duration_min", "max_scrolls"],
        "defaults": {"duration_min": 6, "max_scrolls": 15},
        "stages": ["warmup", "steady", "engage", "post_ready"],
        "risk_level": "low",
    },
    {
        "action": "upvote",
        "description": "While browsing the feed, upvote posts based on upvote_ratio probability.",
        "description_zh": "浏览 Feed 过程中按概率随机点赞",
        "required_params": [],
        "optional_params": ["duration_min", "max_actions", "upvote_ratio"],
        "defaults": {"duration_min": 10, "max_actions": 20, "upvote_ratio": 0.05},
        "stages": ["steady", "engage", "post_ready"],
        "risk_level": "medium",
    },
    {
        "action": "subscribe",
        "description": "Navigate to a subreddit (by name or from recommendations) and tap Join.",
        "description_zh": "进入指定/推荐 Subreddit 并点击 Join 加入",
        "required_params": [],
        "optional_params": ["subreddit_name"],
        "defaults": {},
        "stages": ["steady", "engage", "post_ready"],
        "risk_level": "low",
    },
    {
        "action": "comment",
        "description": "Open a post and leave a short comment from predefined templates.",
        "description_zh": "打开帖子并发表简短模板化评论",
        "required_params": [],
        "optional_params": ["max_actions", "comment_templates"],
        "defaults": {"max_actions": 2, "comment_templates": ["Nice!", "Thanks for sharing", "Interesting"]},
        "stages": ["engage", "post_ready"],
        "risk_level": "high",
    },
    {
        "action": "profile_check",
        "description": "Navigate to the profile page, read karma value and account name, report to server.",
        "description_zh": "进入 Profile 页，读取 karma 值和账号名，上报服务器",
        "required_params": [],
        "optional_params": [],
        "defaults": {},
        "stages": ["warmup", "steady", "engage", "post_ready"],
        "risk_level": "low",
    },
]

_ACTION_MAP: dict[str, str] = {
    "browse": "actions.browse",
    "search": "actions.search",
    "upvote": "actions.upvote",
    "subscribe": "actions.subscribe",
    "comment": "actions.comment",
    "profile_check": "actions.profile_check",
}


def get_action_handler(action_name: str) -> Callable | None:
    """Return the execute() callable for the given action name, or None."""
    mod_name = _ACTION_MAP.get(action_name)
    if not mod_name:
        return None
    try:
        import importlib
        mod = importlib.import_module(f"..{mod_name}", package=__name__)
        return getattr(mod, "execute", None)
    except Exception:
        return None


def catalog_for_prompt() -> str:
    """Return a compact text block suitable for injecting into an LLM prompt."""
    lines = []
    for a in ACTION_CATALOG:
        params = a["required_params"] + a["optional_params"]
        param_str = ", ".join(params) if params else "(none)"
        lines.append(
            f"- {a['action']}: {a['description']} | "
            f"params: {param_str} | stages: {','.join(a['stages'])} | risk: {a['risk_level']}"
        )
    return "\n".join(lines)
