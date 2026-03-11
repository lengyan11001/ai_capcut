#!/usr/bin/env python3
"""Reddit fetch + filter helper for 3s clip generator.

This script fetches posts from one or more subreddits using Reddit's
public JSON endpoints, applies our selection rules, and outputs a
structured JSON file that later steps can turn into HTML / video.

Selection rules (current defaults):
  - Time window: created_utc in [now-48h, now-24h)
  - Score (upvotes): >= 500
  - num_comments:    >= 100
  - Content type:    single wide image post only
      * Exclude: ads, videos, galleries, gifs, too-narrow images, pure text

The output JSON (per post) is intentionally small and stable so that
other scripts can build on top of it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional
from urllib.error import URLError, HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


# Pretend to be a real desktop Chrome to avoid simple bot blocking.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
BASE_URL = "https://www.reddit.com"

# Optional TikHub integration. If TIKHUB_API_KEY is set in env, we will
# fetch posts via TikHub's Reddit APP API instead of direct reddit.com JSON.
TIKHUB_API_KEY = os.environ.get("TIKHUB_API_KEY")
# beta.tikhub.io 是你在浏览器里验证过可用的域名，这里也统一用它。
TIKHUB_BASE = "https://beta.tikhub.io"
ROOT_DIR = Path(__file__).resolve().parent.parent
TIKHUB_CACHE_DIR = ROOT_DIR / ".cache" / "tikhub"
TIKHUB_CACHE_TTL_SEC = int(os.environ.get("TIKHUB_CACHE_TTL_SEC", "21600"))  # default 6h


@dataclass
class TopComment:
    author: str
    body: str
    score: int


@dataclass
class PostRecord:
    id: str
    subreddit: str
    title: str
    selftext: str
    author: str
    score: int
    num_comments: int
    created_utc: float
    permalink: str
    image_url: str
    image_width: int
    image_height: int
    top_comment: Optional[TopComment]


def _http_get_json(url: str) -> Any:
    """Small helper around urlopen that always returns parsed JSON."""
    headers = {
        "User-Agent": USER_AGENT,
        # These make us look more like a normal browser XHR/fetch.
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=15) as resp:
            data = resp.read()
    except (URLError, HTTPError) as exc:
        print(f"[warn] request failed {url}: {exc}", file=sys.stderr)
        return None
    try:
        return json.loads(data)
    except json.JSONDecodeError as exc:
        print(f"[warn] JSON decode failed {url}: {exc}", file=sys.stderr)
        return None


def _tikhub_get_json(path: str, params: dict) -> Any:
    """GET helper for TikHub API."""
    if not TIKHUB_API_KEY:
        return None
    qs = urlencode(params, doseq=True)
    url = f"{TIKHUB_BASE}{path}"
    if qs:
        url = f"{url}?{qs}"

    # On-disk cache to avoid repeated charges.
    try:
        TIKHUB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        cache_path = TIKHUB_CACHE_DIR / f"{key}.json"
        if cache_path.exists():
            age = time.time() - cache_path.stat().st_mtime
            if age >= 0 and age <= TIKHUB_CACHE_TTL_SEC:
                return json.loads(cache_path.read_text("utf-8"))
    except Exception:
        pass

    headers = {
        "Authorization": f"Bearer {TIKHUB_API_KEY}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=20) as resp:
            data = resp.read()
    except (URLError, HTTPError) as exc:
        print(f"[warn] TikHub request failed {url}: {exc}", file=sys.stderr)
        return None
    try:
        parsed = json.loads(data)
        try:
            cache_path.write_text(json.dumps(parsed, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        return parsed
    except json.JSONDecodeError as exc:
        print(f"[warn] TikHub JSON decode failed {url}: {exc}", file=sys.stderr)
        return None


def _fetch_top_comment_via_tikhub(post_id: str) -> Optional[TopComment]:
    """通过 TikHub 的评论接口获取某个帖子的最高赞评论。

    post_id: Reddit 帖子短 ID，例如 '1rpuvn5'，函数内部会自动加上 t3_ 前缀。
    """
    if not TIKHUB_API_KEY:
        return None
    data = _tikhub_get_json(
        "/api/v1/reddit/app/fetch_post_comments",
        {
            "post_id": f"t3_{post_id}",
            "sort_type": "TOP",
        },
    )
    if not data:
        return None

    post_info = (data.get("data") or {}).get("postInfoById") or {}
    forest = (post_info.get("commentForest") or {}).get("trees") or []

    best: Optional[TopComment] = None
    best_score = -1

    for tree in forest:
        node = tree.get("node") or {}
        if node.get("__typename") != "Comment":
            continue
        if node.get("isStickied"):
            continue
        body = ((node.get("content") or {}).get("markdown") or "").strip()
        if not body:
            continue
        author = (node.get("authorInfo") or {}).get("name") or ""
        score = int(node.get("score") or 0)
        if score > best_score:
            best_score = score
            best = TopComment(author=author, body=body, score=score)

    return best


def _iter_listing_children(listing_json: Any) -> Iterable[dict]:
    if not isinstance(listing_json, dict):
        return []
    data = listing_json.get("data") or {}
    children = data.get("children") or []
    for child in children:
        if isinstance(child, dict):
            yield child.get("data") or {}


def _pick_preview_image(post: dict) -> tuple[str, int, int] | tuple[None, int, int]:
    """Return (url, width, height) for the main preview image, if any."""
    # Prefer preview.images[0].source
    preview = post.get("preview") or {}
    images = preview.get("images") or []
    if images:
        source = images[0].get("source") or {}
        url = source.get("url")
        w = int(source.get("width") or 0)
        h = int(source.get("height") or 0)
        if url and w > 0 and h > 0:
            # Reddit may HTML-encode '&amp;'
            url = url.replace("&amp;", "&")
            return url, w, h

    # Fallback: url_overridden_by_dest if looks like an image
    url = post.get("url_overridden_by_dest") or post.get("url")
    if isinstance(url, str) and url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        return url, 0, 0

    return None, 0, 0


def _is_disallowed_type(post: dict) -> bool:
    """Return True if this post should be excluded by media type."""
    if post.get("promoted") or post.get("is_video_ad"):
        return True

    if post.get("over_18"):
        return True

    post_hint = post.get("post_hint") or ""

    # Exclude videos / rich embeds
    if post.get("is_video") or post_hint in {"hosted:video", "rich:video"}:
        return True

    # Exclude galleries / multi-image
    if post.get("is_gallery") or post.get("gallery_data"):
        return True

    url = (post.get("url_overridden_by_dest") or "").lower()
    if url.endswith((".gif", ".gifv")):
        return True

    # Exclude pure text (self) posts (no preview / image)
    if post_hint == "self" and not post.get("preview"):
        return True

    # Narrow / tiny images handled separately via dimensions.
    return False


def _in_time_window(created_utc: float, now_ts: float, min_hours: int, max_hours: int) -> bool:
    age_hours = (now_ts - created_utc) / 3600.0
    return min_hours <= age_hours < max_hours


def _fetch_top_comment(subreddit: str, post_id: str) -> Optional[TopComment]:
    url = f"{BASE_URL}/comments/{quote(post_id)}.json?sort=top&limit=5"
    data = _http_get_json(url)
    if not isinstance(data, list) or len(data) < 2:
        return None

    # Comments are in the second listing.
    comments_listing = data[1]
    for child in _iter_listing_children(comments_listing):
        # Skip stickied / mod comments
        if child.get("stickied") or child.get("distinguished") in {"moderator", "admin"}:
            continue
        body = (child.get("body") or "").strip()
        if not body:
            continue
        score = int(child.get("score") or 0)
        author = child.get("author") or ""
        # Length sanity check (20–200 chars)
        if len(body) < 20 or len(body) > 2000:
            continue
        return TopComment(author=author, body=body, score=score)
    return None


def _fetch_subreddit_via_reddit_api(
    subreddit: str,
    now_ts: float,
    min_hours: int,
    max_hours: int,
    min_score: int,
    min_comments: int,
    min_image_width: int,
    min_aspect_ratio: float,
) -> List[PostRecord]:
    """Fetch and filter posts for a single subreddit using reddit.com JSON."""
    encoded = quote(subreddit)
    # Use 'top' over the last week as a superset, then filter by time window.
    url = f"{BASE_URL}/r/{encoded}/top.json?t=week&limit=100"
    listing = _http_get_json(url)
    if listing is None:
        return []

    results: List[PostRecord] = []
    for post in _iter_listing_children(listing):
        try:
            if _is_disallowed_type(post):
                continue

            created_utc = float(post.get("created_utc") or 0.0)
            if not _in_time_window(created_utc, now_ts, min_hours=min_hours, max_hours=max_hours):
                continue

            score = int(post.get("score") or 0)
            num_comments = int(post.get("num_comments") or 0)
            if score < min_score or num_comments < min_comments:
                continue

            img_url, w, h = _pick_preview_image(post)
            if not img_url:
                continue

            # Filter narrow / tiny images.
            if w and (w < min_image_width or (h and (w / float(h)) < min_aspect_ratio)):
                continue

            sub = post.get("subreddit") or subreddit
            post_id = post.get("id") or ""
            record = PostRecord(
                id=post_id,
                subreddit=sub,
                title=post.get("title") or "",
                selftext=post.get("selftext") or "",
                author=post.get("author") or "",
                score=score,
                num_comments=num_comments,
                created_utc=created_utc,
                permalink=BASE_URL + (post.get("permalink") or f"/r/{sub}/comments/{post_id}"),
                image_url=img_url,
                image_width=int(w or 0),
                image_height=int(h or 0),
                top_comment=None,  # filled below
            )

            record.top_comment = _fetch_top_comment(sub, post_id)
            if not record.top_comment:
                continue

            results.append(record)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[warn] skip post due to error: {exc}", file=sys.stderr)
            continue

    return results


def _fetch_subreddit_via_tikhub(
    subreddit: str,
    now_ts: float,
    min_hours: int,
    max_hours: int,
    min_score: int,
    min_comments: int,
    min_image_width: int,
    min_aspect_ratio: float,
) -> List[PostRecord]:
    """用 TikHub 的 /api/v1/reddit/app/fetch_subreddit_feed 抓指定版块的帖子。

    使用 NEW 排序并支持翻页，直到：
      - 发现帖子时间早于 max_hours，或
      - 没有下一页。
    然后在全部结果里按我们的时间窗口 / 点赞 / 评论 / 图片规则过滤。
    """
    results: List[PostRecord] = []
    after: Optional[str] = None

    while True:
        params = {
            "subreddit_name": subreddit,
            "sort": "NEW",
            "need_format": "true",
        }
        if after:
            params["after"] = after

        data = _tikhub_get_json("/api/v1/reddit/app/fetch_subreddit_feed", params)
        if not data:
            break

        feed = (data.get("data") or {}).get("subredditfeed") or {}
        sub_v3 = feed.get("subredditV3") or {}
        elements = sub_v3.get("elements") or {}
        edges = elements.get("edges") or []

        if not edges:
            break

        stop_due_to_time = False

        for edge in edges:
            try:
                node = edge.get("node") or {}
                group_id = node.get("groupId") or ""
                if not group_id.startswith("t3_"):
                    continue
                if "adPayload" in node:
                    continue

                cells = node.get("cells") or []
                meta: dict = {}
                title = ""
                media: dict = {}
                actions: dict = {}

                for cell in cells:
                    if "createdAt" in cell:
                        meta = cell
                    elif "media" in cell:
                        media = cell.get("media") or {}
                    elif "commentCount" in cell or "score" in cell:
                        actions = cell
                    elif "title" in cell:
                        title = cell.get("title") or title

                created_at = meta.get("createdAt")
                if not created_at:
                    continue
                try:
                    ts = created_at.replace("Z", "+00:00")
                    if ts.endswith("+0000"):
                        ts = ts[:-5] + "+00:00"
                    dt = datetime.fromisoformat(ts)
                    created_utc = dt.replace(tzinfo=timezone.utc).timestamp()
                except Exception:
                    continue

                age_hours = (now_ts - created_utc) / 3600.0
                if not _in_time_window(
                    created_utc, now_ts, min_hours=min_hours, max_hours=max_hours
                ):
                    if age_hours > max_hours:
                        stop_due_to_time = True
                    continue

                score = int(actions.get("score") or 0)
                num_comments = int(actions.get("commentCount") or 0)
                if score < min_score or num_comments < min_comments:
                    continue

                img_url = ""
                w = h = 0
                if media:
                    img_url = media.get("path") or ""
                    lower_url = img_url.lower()
                    if lower_url.endswith(".gif") or "format=mp4" in lower_url:
                        continue
                    size = media.get("size") or {}
                    w = int(size.get("width") or 0)
                    h = int(size.get("height") or 0)
                if not img_url:
                    continue
                if w and (w < min_image_width or (h and (w / float(h)) < min_aspect_ratio)):
                    continue

                author = (meta.get("detailsString") or "").replace("u/", "").strip()
                permalink = meta.get("detailsLink") or ""
                if permalink and not permalink.startswith("http"):
                    permalink = f"https://www.reddit.com/r/{subreddit}"

                post_id = group_id.replace("t3_", "")
                top_comment = _fetch_top_comment_via_tikhub(post_id)

                results.append(
                    PostRecord(
                        id=post_id,
                        subreddit=subreddit,
                        title=title,
                        selftext="",
                        author=author,
                        score=score,
                        num_comments=num_comments,
                        created_utc=created_utc,
                        permalink=permalink,
                        image_url=img_url,
                        image_width=w,
                        image_height=h,
                        top_comment=top_comment,
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive
                print(f"[warn] skip TikHub edge due to error: {exc}", file=sys.stderr)
                continue

        if stop_due_to_time:
            break

        page_info = elements.get("pageInfo") or {}
        new_after = page_info.get("endCursor")
        if not new_after or new_after == after:
            break
        after = new_after

    return results


def fetch_subreddit(
    subreddit: str,
    now_ts: float,
    min_hours: int = 24,
    max_hours: int = 48,
    min_score: int = 500,
    min_comments: int = 100,
    min_image_width: int = 600,
    min_aspect_ratio: float = 0.6,
) -> List[PostRecord]:
    """Fetch and filter posts for a single subreddit.

    Priority:
      1. If TIKHUB_API_KEY is set, use TikHub Reddit APP API.
      2. Fallback to reddit.com JSON endpoints (may 403 in some regions).
    """
    if TIKHUB_API_KEY:
        return _fetch_subreddit_via_tikhub(
            subreddit=subreddit,
            now_ts=now_ts,
            min_hours=min_hours,
            max_hours=max_hours,
            min_score=min_score,
            min_comments=min_comments,
            min_image_width=min_image_width,
            min_aspect_ratio=min_aspect_ratio,
        )
    return _fetch_subreddit_via_reddit_api(
        subreddit=subreddit,
        now_ts=now_ts,
        min_hours=min_hours,
        max_hours=max_hours,
        min_score=min_score,
        min_comments=min_comments,
        min_image_width=min_image_width,
        min_aspect_ratio=min_aspect_ratio,
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reddit_fetch",
        description="Fetch and filter Reddit posts for 3s clips.",
    )
    parser.add_argument(
        "--subs",
        required=True,
        help="Comma-separated list of subreddit names (without r/ prefix).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON path for collected posts.",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=500,
        help="Minimum score (upvotes) to keep a post (default: 500).",
    )
    parser.add_argument(
        "--min-comments",
        type=int,
        default=100,
        help="Minimum number of comments to keep a post (default: 100).",
    )
    parser.add_argument(
        "--min-hours",
        type=int,
        default=24,
        help="Minimum age in hours (default: 24).",
    )
    parser.add_argument(
        "--max-hours",
        type=int,
        default=48,
        help="Maximum age in hours (default: 48).",
    )

    args = parser.parse_args(argv)

    now_ts = time.time()
    subs = [s.strip() for s in args.subs.split(",") if s.strip()]
    if not subs:
        print("No subreddits provided.", file=sys.stderr)
        return 1

    all_posts: List[PostRecord] = []
    for sub in subs:
        print(f"[info] Fetching r/{sub} ...")
        posts = fetch_subreddit(
            subreddit=sub,
            now_ts=now_ts,
            min_hours=args.min_hours,
            max_hours=args.max_hours,
            min_score=args.min_score,
            min_comments=args.min_comments,
        )
        print(f"  -> {len(posts)} posts kept after filtering.")
        all_posts.extend(posts)

    # Sort by score descending, then by created_utc desc.
    all_posts.sort(key=lambda p: (p.score, p.created_utc), reverse=True)

    out_path = args.output
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "subreddits": subs,
        "count": len(all_posts),
        "posts": [
            {
                **asdict(p),
                "top_comment": asdict(p.top_comment) if p.top_comment else None,
            }
            for p in all_posts
        ],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[done] {len(all_posts)} posts written to {out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

