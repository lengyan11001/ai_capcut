#!/usr/bin/env python3
"""
YouTube policy pre-check (conservative).

Goal: Before generating videos from scraped Reddit content, detect likely
violations of YouTube Community Guidelines and skip those items.

We implement a conservative, text-only heuristic checker that flags content
based on keyword/regex matches across title + post text + comment text.

Primary sources (YouTube Help):
- Hate speech policy: https://support.google.com/youtube/answer/2801939
- Harassment & cyberbullying: https://support.google.com/youtube/answer/2802268
- Suicide/self-harm/eating disorders: https://support.google.com/youtube/answer/2802245

Note: This is NOT a substitute for human review or YouTube's own enforcement.
We prefer false positives (skip) over false negatives (upload risky content).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Pattern, Tuple


@dataclass(frozen=True)
class PolicyMatch:
    category: str
    rule_id: str
    excerpt: str


def _compile(patterns: Iterable[str]) -> List[Pattern[str]]:
    out: List[Pattern[str]] = []
    for p in patterns:
        p = (p or "").strip()
        if not p:
            continue
        out.append(re.compile(p))
    return out


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text("utf-8"))


def _find_first_excerpt(text: str, needle: str, window: int = 40) -> str:
    lower = text.lower()
    n = needle.lower()
    i = lower.find(n)
    if i < 0:
        return ""
    start = max(0, i - window)
    end = min(len(text), i + len(needle) + window)
    return text[start:end].replace("\n", " ").strip()


class YouTubePolicyChecker:
    def __init__(self, rules: dict):
        self.rules = rules or {}

        self.blocked_substrings_zh = [s for s in self.rules.get("blocked_substrings_zh", []) if str(s).strip()]
        self.blocked_substrings_en = [s for s in self.rules.get("blocked_substrings_en", []) if str(s).strip()]
        self.blocked_regex = _compile(self.rules.get("blocked_regex", []))
        self.whitelist_substrings = [str(s).strip().lower() for s in self.rules.get("whitelist_substrings", []) if str(s).strip()]

        # Optional categorized rules for clearer reporting.
        self.categorized = self.rules.get("categorized_rules", {}) or {}
        self.cat_substrings = {
            k: [str(s).strip() for s in (v.get("blocked_substrings") or []) if str(s).strip()]
            for k, v in self.categorized.items()
        }
        self.cat_regex = {k: _compile(v.get("blocked_regex", []) or []) for k, v in self.categorized.items()}

    @classmethod
    def from_json_file(cls, path: Path) -> "YouTubePolicyChecker":
        return cls(_load_json(path))

    def check_text(self, text: str) -> Tuple[bool, List[PolicyMatch]]:
        if not text:
            return True, []
        t = text
        lower = t.lower()

        # Whitelist shortcuts (kept compatible with existing config behavior)
        for w in self.whitelist_substrings:
            if w and w in lower:
                return True, []

        matches: List[PolicyMatch] = []

        for s in self.blocked_substrings_zh:
            if s and s in t:
                matches.append(PolicyMatch(category="generic", rule_id=f"substr_zh:{s}", excerpt=_find_first_excerpt(t, s)))

        for s in self.blocked_substrings_en:
            if s and s.lower() in lower:
                matches.append(PolicyMatch(category="generic", rule_id=f"substr_en:{s}", excerpt=_find_first_excerpt(t, s)))

        for rg in self.blocked_regex:
            m = rg.search(t)
            if m:
                excerpt = t[max(0, m.start() - 40) : min(len(t), m.end() + 40)].replace("\n", " ").strip()
                matches.append(PolicyMatch(category="generic", rule_id=f"regex:{rg.pattern}", excerpt=excerpt))

        for cat, subs in self.cat_substrings.items():
            for s in subs:
                if s and s.lower() in lower:
                    matches.append(PolicyMatch(category=cat, rule_id=f"{cat}:substr:{s}", excerpt=_find_first_excerpt(t, s)))
            for rg in self.cat_regex.get(cat, []):
                m = rg.search(t)
                if m:
                    excerpt = t[max(0, m.start() - 40) : min(len(t), m.end() + 40)].replace("\n", " ").strip()
                    matches.append(PolicyMatch(category=cat, rule_id=f"{cat}:regex:{rg.pattern}", excerpt=excerpt))

        return (len(matches) == 0), matches


def default_conservative_rules() -> dict:
    """
    Conservative add-on rules covering key guideline areas mentioned above.
    Intended as a baseline; project can extend via JSON.
    """
    return {
        "categorized_rules": {
            # Hate speech / protected groups (policy above)
            "hate_harassment": {
                "blocked_substrings": [
                    # keep list small; rely on project-specific expansion
                    "kys",  # also covered by regex; keep for plain matches
                ],
                "blocked_regex": [
                    r"(?i)\b(kill\s+yourself)\b",
                    r"(?i)\b(go\s+die)\b",
                    r"(?i)\b(i\s+hope\s+you\s+die)\b",
                ],
            },
            # Self-harm/suicide (policy above)
            "self_harm": {
                "blocked_regex": [
                    r"(?i)\bhow\s+to\s+kill\s+yourself\b",
                    r"(?i)\bhow\s+to\s+self\s*harm\b",
                    r"(?i)\bcut\s+yourself\b",
                ]
            },
            # Child safety / sexual content involving minors (policy above)
            "child_safety": {
                "blocked_regex": [
                    r"(?i)\bunder\s*age\b",
                    r"(?i)\bmolest(ing|er|ation)?\b",
                    r"(?i)\bpedoph(ile|ilia|)\b",
                    r"(?i)\bchild\s+molest(er|ation)?\b",
                ]
            },
            # Regulated goods: drugs/weapons (general guideline area)
            "regulated_goods": {
                "blocked_regex": [
                    r"(?i)\bhow\s+to\s+buy\s+(weed|cocaine|heroin|meth)\b",
                    r"(?i)\bwhere\s+to\s+buy\s+(weed|cocaine|heroin|meth)\b",
                    r"(?i)\bbuild\s+(a\s+)?gun\b",
                ]
            },
        }
    }


def merge_rules(base: dict, extra: Optional[dict]) -> dict:
    if not extra:
        return base
    # shallow merge with categorized nested merge
    out = dict(base)
    for k, v in extra.items():
        if k != "categorized_rules":
            out[k] = v
            continue
        merged_cats = dict(base.get("categorized_rules", {}) or {})
        for cat, cat_rules in (v or {}).items():
            prev = merged_cats.get(cat, {}) or {}
            merged = dict(prev)
            merged.update(cat_rules or {})
            merged_cats[cat] = merged
        out["categorized_rules"] = merged_cats
    return out


def build_checker(filters_json_path: Path) -> YouTubePolicyChecker:
    """
    Build checker from existing youtube_safety_filters.json and conservative defaults.
    """
    base = default_conservative_rules()
    extra = _load_json(filters_json_path) if filters_json_path.exists() else {}
    rules = merge_rules(base, extra)
    return YouTubePolicyChecker(rules)

