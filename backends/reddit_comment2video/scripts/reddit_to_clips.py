#!/usr/bin/env python3
"""reddit_to_clips: end-to-end 3s clip generator.

Pipeline:
  1. Load config (reddit_3s_config.json)
  2. Fetch posts per subreddit via reddit_fetch.fetch_subreddit
  3. Apply YouTube-safety text filtering
  4. Pick up to max_clips posts (default 2)
  5. For each post:
       - assign persona (avatar/name) from config
       - pick random background video + background audio
       - generate HTML file from template.html
  6. Use Playwright to record each HTML for 3 seconds → WebM
  7. Use ffmpeg to mux WebM + bgm (3s) → MP4 clips
"""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
import tempfile
import shutil
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional


ROOT_DIR = Path(__file__).resolve().parent.parent
PLAYWRIGHT_CACHE = Path.home() / "Library" / "Caches" / "ms-playwright"


def resolve_ffmpeg() -> str:
    local = ROOT_DIR / "bin" / "ffmpeg"
    if local.exists():
        return str(local)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    bundled = PLAYWRIGHT_CACHE / "ffmpeg-1011" / "ffmpeg-mac"
    if bundled.exists():
        return str(bundled)
    # Fallback: any ffmpeg-* directory
    if PLAYWRIGHT_CACHE.exists():
        for d in sorted(PLAYWRIGHT_CACHE.glob("ffmpeg-*"), reverse=True):
            candidate = d / "ffmpeg-mac"
            if candidate.exists():
                return str(candidate)
    raise FileNotFoundError(
        "ffmpeg not found. Install ffmpeg or run `python3 -m playwright install` "
        "to download bundled ffmpeg."
    )


@dataclass
class Persona:
    youtube_channel_id: str
    name: str
    avatar_path: Path


@dataclass
class Clip:
    id: str
    subreddit: str
    title: str
    post_text: str
    post_image_url: str
    post_image: Optional[Path]
    author: str
    score: int
    permalink: str
    comment_text: str
    persona: Persona
    bg_video: Path
    bg_audio: Path


def load_config(path: Path) -> dict:
    return json.loads(path.read_text("utf-8"))


def load_safety_filters(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text("utf-8"))


def build_persona_map(cfg: dict) -> Dict[str, Persona]:
    personas: Dict[str, Persona] = {}
    for item in cfg.get("subreddits", []):
        name = item.get("name")
        if not name:
            continue
        personas[name.lower()] = Persona(
            youtube_channel_id=item.get("youtube_channel_id", ""),
            name=item.get("comment_persona_name", ""),
            avatar_path=ROOT_DIR / item.get("comment_persona_avatar_path", ""),
        )
    return personas


def list_media_files(dir_path: Path, exts: List[str]) -> List[Path]:
    if not dir_path.exists():
        return []
    files: List[Path] = []
    for p in dir_path.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            files.append(p)
    return sorted(files)


def make_safety_checker(filters: dict):
    blocked_zh = [s.strip() for s in filters.get("blocked_substrings_zh", []) if s.strip()]
    blocked_en = [s.strip() for s in filters.get("blocked_substrings_en", []) if s.strip()]
    blocked_regex = [re.compile(p) for p in filters.get("blocked_regex", [])]
    whitelist = [s.strip().lower() for s in filters.get("whitelist_substrings", []) if s.strip()]

    def is_safe(text: str) -> bool:
        if not text:
            return True
        lower = text.lower()
        for w in whitelist:
            if w in lower:
                return True
        for s in blocked_zh:
            if s in text:
                return False
        for s in blocked_en:
            if s.lower() in lower:
                return False
        for rg in blocked_regex:
            if rg.search(text):
                return False
        return True

    return is_safe


def truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^\)]+\)")


def sanitize_comment_text(text: str) -> str:
    """Normalize comment text for display and filtering.

    - Remove markdown image placeholders like '![img](...)'
    - Collapse whitespace/newlines so empty lines don't consume clamp height
    """
    if not text:
        return ""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = _MD_IMAGE_RE.sub("", t)
    lines = [ln.strip() for ln in t.split("\n")]
    lines = [ln for ln in lines if ln]  # drop empty lines
    t = " ".join(lines)
    # collapse repeated spaces
    t = re.sub(r"\s+", " ", t).strip()
    return t


def is_textual_comment(text: str) -> bool:
    """Heuristic: skip image/emoji-only comments after sanitization."""
    t = sanitize_comment_text(text)
    if not t:
        return False
    # Require some letters/digits to avoid pure emoji/punctuation
    return bool(re.search(r"[A-Za-z0-9]", t))


def download_image(url: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
        if not data:
            raise RuntimeError("empty image response")
        out_path.write_bytes(data)
    return out_path


def _fetch_posts_via_cli(
    subreddit: str,
    min_hours: int,
    max_hours: int,
    min_score: int,
    min_comments: int,
) -> List[dict]:
    """Call reddit_fetch.py via subprocess and return posts list.

    NOTE: This path uses Reddit's public JSON endpoints, which may now
    return 403 in many environments. For more robust scraping that
    looks like a real browser, see _fetch_posts_via_dom().
    """
    tmp = Path(tempfile.mkstemp(suffix=".json")[1])
    cmd = [
        "python3",
        str((ROOT_DIR / "scripts" / "reddit_fetch.py")),
        "--subs",
        subreddit,
        "--min-hours",
        str(min_hours),
        "--max-hours",
        str(max_hours),
        "--min-score",
        str(min_score),
        "--min-comments",
        str(min_comments),
        "--output",
        str(tmp),
    ]
    subprocess.run(cmd, check=True)
    data = json.loads(tmp.read_text("utf-8"))
    tmp.unlink(missing_ok=True)
    return data.get("posts", [])


def _fetch_posts_via_dom(
    subreddit: str,
    min_hours: int,
    max_hours: int,
    min_score: int,
    min_comments: int,
) -> List[dict]:
    """Use Playwright + DOM 来抓取帖子列表和评论，不走 JSON API。

    步骤：
      1. 打开 /r/{sub}/top/?t=week 页面，抓前若干个帖子（标题、分数、评论数、创建时间、图片、permalink）。
      2. 对满足过滤条件的帖子，进入详情页抓“第一个正常评论”当作 top comment。
    """
    from playwright.async_api import async_playwright  # type: ignore
    import asyncio
    import time as _time

    now_ts = _time.time()
    posts: List[dict] = []

    async def _run() -> None:
        nonlocal posts
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(
                viewport={"width": 1080, "height": 1920},
            )
            url = f"https://www.reddit.com/r/{subreddit}/top/?t=week"
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            raw_posts = await page.eval_on_selector_all(
                "div[data-testid='post-container']",
                """
                (els) => els.slice(0, 40).map(el => {
                  const titleEl = el.querySelector('h3');
                  const title = titleEl ? titleEl.innerText : '';

                  const authorEl = el.querySelector('a[data-click-id="user"]');
                  const author = authorEl ? authorEl.innerText.replace(/^u\\//, '') : '';

                  const scoreEl = el.querySelector('[id^="vote-arrows-"]') || el.querySelector('[data-click-id="upvote"]')?.parentElement;
                  let scoreText = '';
                  if (scoreEl) {
                    const aria = scoreEl.getAttribute('aria-label') || '';
                    scoreText = aria;
                  }

                  const commentsEl = el.querySelector('a[data-click-id="comments"]');
                  const commentsText = commentsEl ? commentsEl.innerText : '';

                  const timeEl = el.querySelector('a[data-click-id="timestamp"] time[datetime]');
                  const datetimeAttr = timeEl ? timeEl.getAttribute('datetime') : null;

                  const linkEl = el.querySelector('a[data-click-id="body"]');
                  const href = linkEl ? linkEl.getAttribute('href') : null;

                  const imgEl = el.querySelector('img[alt="Post image"], img[alt="Post Image"], img[alt*="image"]');
                  const imgSrc = imgEl ? imgEl.src : null;
                  const imgW = imgEl ? imgEl.naturalWidth || 0 : 0;
                  const imgH = imgEl ? imgEl.naturalHeight || 0 : 0;

                  return {
                    title,
                    author,
                    scoreText,
                    commentsText,
                    datetimeAttr,
                    href,
                    imgSrc,
                    imgW,
                    imgH,
                  };
                })
                """,
            )

            def _parse_int_from_text(t: str) -> int:
                t = (t or "").lower().strip()
                if not t:
                    return 0
                # e.g. "1.2k votes"
                import re as _re

                m = _re.search(r"([0-9]+(?:\\.[0-9]+)?)", t)
                if not m:
                    return 0
                num = float(m.group(1))
                return int(num * 1000) if "k" in t else int(num)

            def _parse_comments_count(t: str) -> int:
                # e.g. "123 comments" / "1.1k comments"
                return _parse_int_from_text(t)

            import datetime as _dt

            candidates: List[dict] = []
            for item in raw_posts or []:
                title = (item.get("title") or "").strip()
                if not title:
                    continue
                datetime_attr = item.get("datetimeAttr")
                if not datetime_attr:
                    continue
                try:
                    created_dt = _dt.datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
                    created_utc = created_dt.timestamp()
                except Exception:
                    continue

                age_hours = (now_ts - created_utc) / 3600.0
                if not (min_hours <= age_hours < max_hours):
                    continue

                score = _parse_int_from_text(item.get("scoreText") or "")
                num_comments = _parse_comments_count(item.get("commentsText") or "")
                if score < min_score or num_comments < min_comments:
                    continue

                img = item.get("imgSrc")
                if not img:
                    continue

                href = item.get("href") or ""
                if href.startswith("/"):
                    permalink = "https://www.reddit.com" + href
                else:
                    permalink = href

                candidates.append(
                    {
                        "title": title,
                        "author": item.get("author") or "",
                        "score": score,
                        "num_comments": num_comments,
                        "created_utc": created_utc,
                        "permalink": permalink,
                        "image_url": img,
                        "image_width": int(item.get("imgW") or 0),
                        "image_height": int(item.get("imgH") or 0),
                    }
                )

            # 按分数排序，依次打开详情页抓 top comment。
            candidates.sort(key=lambda x: x["score"], reverse=True)
            results: List[dict] = []

            for cand in candidates:
                if len(results) >= 50:
                    break
                post_page = await browser.new_page(viewport={"width": 1080, "height": 1920})
                await post_page.goto(cand["permalink"], wait_until="networkidle")
                await post_page.wait_for_timeout(2000)

                top_comment = await post_page.eval_on_selector_all(
                    'div[data-test-id="comment"]',
                    """
                    (els) => {
                      for (const el of els) {
                        // 跳过置顶 / mod 评论（简单过滤）
                        if (el.innerText.toLowerCase().includes('moderator')) continue;
                        const bodyEl = el.querySelector('p');
                        const body = bodyEl ? bodyEl.innerText.trim() : '';
                        if (!body || body.length < 20) continue;
                        const authorEl = el.querySelector('a[data-click-id="user"]');
                        const author = authorEl ? authorEl.innerText.replace(/^u\\//, '') : '';
                        const scoreEl = el.querySelector('[id^="vote-arrows-"]') || el.querySelector('[data-click-id="upvote"]')?.parentElement;
                        let scoreText = '';
                        if (scoreEl) {
                          const aria = scoreEl.getAttribute('aria-label') || '';
                          scoreText = aria;
                        }
                        return { body, author, scoreText };
                      }
                      return null;
                    }
                    """,
                )
                await post_page.close()

                body = ""
                author = ""
                score_comment = 0
                if top_comment:
                    body = (top_comment.get("body") or "").strip()
                    author = top_comment.get("author") or ""
                    score_comment = _parse_int_from_text(top_comment.get("scoreText") or "")

                if not body:
                    # 没有合适评论就跳过
                    continue

                cand["top_comment"] = {
                    "author": author,
                    "body": body,
                    "score": score_comment,
                }
                results.append(cand)

            await browser.close()
            posts = results

    asyncio.run(_run())
    return posts


def pick_clips(
    cfg: dict,
    safety_filters: dict,
    max_clips: int,
) -> List[Clip]:
    time_cfg = cfg.get("time_window_hours", {})
    min_hours = int(time_cfg.get("min", 24))
    max_hours = int(time_cfg.get("max", 48))
    pf = cfg.get("post_filters", {})
    min_score = int(pf.get("min_score", 500))
    min_comments = int(pf.get("min_num_comments", 100))

    personas = build_persona_map(cfg)
    bg_dir = ROOT_DIR / cfg.get("background_videos_dir", "")
    audio_dir = ROOT_DIR / cfg.get("background_audio_dir", "")
    bg_videos_all = list_media_files(bg_dir, [".mp4", ".mov", ".mkv"])
    bg_audios_all = list_media_files(audio_dir, [".m4a", ".mp3", ".wav"])

    if not bg_videos_all:
        raise SystemExit(f"未找到背景视频: {bg_dir}")
    if not bg_audios_all:
        raise SystemExit(f"未找到背景音乐: {audio_dir}")

    is_safe = make_safety_checker(safety_filters)
    # YouTube policy pre-check (conservative): skip risky content before video generation.
    try:
        from youtube_policy_check import build_checker  # type: ignore

        policy_checker = build_checker(ROOT_DIR / cfg.get("youtube_safety_filters_path", ""))
    except Exception:
        policy_checker = None

    # 现有 3 个博主：按照 subreddits 的顺序，与背景视频/音频列表
    # 的第 1/2/3 个一一对应；若素材不足则回退到随机选择。
    per_sub_assets: Dict[str, tuple[Path, Path]] = {}
    for idx, sub_cfg in enumerate(cfg.get("subreddits", [])):
        sub_name = sub_cfg.get("name")
        if not sub_name:
            continue
        if idx < len(bg_videos_all):
            v = bg_videos_all[idx]
        else:
            v = random.choice(bg_videos_all)
        if idx < len(bg_audios_all):
            a = bg_audios_all[idx]
        else:
            a = random.choice(bg_audios_all)
        per_sub_assets[sub_name.lower()] = (v, a)

    # 每板块最多准备 max_clips*2 条候选，便于后续录屏/合成失败时仍有足够条数达标
    target = max_clips or int(cfg.get("default_max_clips", 2))
    per_sub_max = max(target * 2, target)

    clips: List[Clip] = []
    for sub_cfg in cfg.get("subreddits", []):
        sub_name = sub_cfg.get("name")
        if not sub_name:
            continue
        persona = personas.get(sub_name.lower())
        if not persona:
            continue
        sub_assets = per_sub_assets.get(sub_name.lower())
        posts = _fetch_posts_via_cli(
            subreddit=sub_name,
            min_hours=min_hours,
            max_hours=max_hours,
            min_score=min_score,
            min_comments=min_comments,
        )
        per_sub_count = 0
        for p in posts:
            if per_sub_count >= per_sub_max:
                break
            top_comment = p.get("top_comment") or {}
            raw_comment_body = top_comment.get("body", "") or ""
            if raw_comment_body and not is_textual_comment(raw_comment_body):
                continue
            comment_body = sanitize_comment_text(raw_comment_body)
            text_all = f"{p.get('title','')}\n{p.get('selftext','')}\n{comment_body}"
            if not is_safe(text_all):
                continue
            if policy_checker is not None:
                ok, matches = policy_checker.check_text(text_all)
                if not ok:
                    # Keep it short; detailed match list would be noisy.
                    cats = sorted({m.category for m in matches})
                    print(f"[skip] youtube_policy category={','.join(cats)} post_id={p.get('id','')}")
                    continue
            post_text = p.get("selftext") or ""
            combined = (p.get("title", "").strip() + "\n" + post_text.strip()).strip()
            combined = truncate(combined, 220)
            comment_text = truncate(comment_body, 180)
            image_url = p.get("image_url") or ""
            if not image_url:
                continue
            if sub_assets:
                bg_video, bg_audio = sub_assets
            else:
                bg_video = random.choice(bg_videos_all)
                bg_audio = random.choice(bg_audios_all)
            clips.append(
                Clip(
                    id=p.get("id", ""),
                    subreddit=p.get("subreddit", sub_name),
                    title=p.get("title", ""),
                    post_text=combined,
                    post_image_url=image_url,
                    post_image=None,
                    author=p.get("author", ""),
                    score=int(p.get("score", 0)),
                    permalink=p.get("permalink", ""),
                    comment_text=comment_text,
                    persona=persona,
                    bg_video=bg_video,
                    bg_audio=bg_audio,
                )
            )
            per_sub_count += 1
    return clips


def ensure_images(work_dir: Path, clips: List[Clip]) -> None:
    """下载帖子图片；失败重试一次，仍失败则从列表中移除该 clip，不中断管线。"""
    assets_dir = work_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    to_remove: List[int] = []
    for i, clip in enumerate(clips):
        if clip.post_image is not None:
            continue
        url = clip.post_image_url
        img_ext = Path(url.split("?")[0]).suffix or ".jpg"
        out = assets_dir / f"{clip.id}{img_ext}"
        try:
            clip.post_image = download_image(url, out)
        except Exception:
            try:
                clip.post_image = download_image(url, out)
            except Exception as e:
                print(f"[warn] image download failed for {clip.id}, skip clip: {e}")
                to_remove.append(i)
                continue
        if not clip.post_image.exists() or clip.post_image.stat().st_size < 1024:
            print(f"[warn] image too small for {clip.id}, skip clip")
            to_remove.append(i)
    for i in reversed(to_remove):
        clips.pop(i)


def fill_comments_via_playwright(clips: List[Clip]) -> None:
    """使用 Playwright 打开贴子详情页，抓取一条合适的顶部评论填充到 clip.comment_text。"""
    if not clips:
        return

    from playwright.async_api import async_playwright  # type: ignore
    import asyncio

    async def _run() -> None:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            for clip in clips:
                # 如果已经有评论文本就跳过
                if clip.comment_text:
                    continue
                if not clip.permalink:
                    continue
                page = await browser.new_page(viewport={"width": 1080, "height": 1920})
                try:
                    await page.goto(clip.permalink, wait_until="networkidle")
                    await page.wait_for_timeout(2000)
                    top_comment = await page.eval_on_selector_all(
                        "div[data-test-id='comment']",
                        """
                        (els) => {
                          for (const el of els) {
                            const bodyEl = el.querySelector('p');
                            const body = bodyEl ? bodyEl.innerText.trim() : '';
                            if (!body || body.length < 10) continue;
                            const authorEl = el.querySelector('a[data-click-id=\"user\"]');
                            const author = authorEl ? authorEl.innerText.replace(/^u\\//, '') : '';
                            return { body, author };
                          }
                          return null;
                        }
                        """,
                    )
                except Exception:
                    top_comment = None
                finally:
                    await page.close()

                if not top_comment:
                    continue
                body = (top_comment.get("body") or "").strip()
                if not body:
                    continue
                if not is_textual_comment(body):
                    continue
                clip.comment_text = truncate(sanitize_comment_text(body), 180)

            await browser.close()

    asyncio.run(_run())


def render_html(work_dir: Path, template_path: Path, clips: List[Clip]) -> None:
    html_dir = work_dir / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    tpl = template_path.read_text("utf-8")
    # Ensure CSS is available next to generated HTML files.
    css_src = ROOT_DIR / "public/reddit-3s-template/styles.css"
    (html_dir / "styles.css").write_text(css_src.read_text("utf-8"), encoding="utf-8")
    for idx, clip in enumerate(clips, start=1):
        if not clip.post_image:
            raise SystemExit(f"Missing post image for clip {clip.id}")
        html = (
            tpl.replace("__BG_VIDEO_SRC__", clip.bg_video.resolve().as_uri())
            .replace("__SUBREDDIT__", clip.subreddit)
            .replace("__AUTHOR__", clip.author)
            .replace("__SCORE__", f"{clip.score}")
            .replace("__TITLE__", clip.title)
            .replace("__POST_TEXT__", clip.post_text)
            .replace("__POST_IMAGE__", clip.post_image.resolve().as_uri())
            .replace("__PERSONA_AVATAR__", clip.persona.avatar_path.resolve().as_uri())
            .replace("__PERSONA_NAME__", clip.persona.name)
            .replace("__COMMENT_TEXT__", clip.comment_text)
        )
        (html_dir / f"clip-{idx:02d}.html").write_text(html, encoding="utf-8")


def record_videos(work_dir: Path, hold_ms: int = 4000) -> None:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
    import asyncio
    import tempfile

    html_dir = work_dir / "html"
    video_dir = work_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    html_files = sorted(html_dir.glob("clip-*.html"))
    if not html_files:
        raise SystemExit(f"未找到 HTML 文件: {html_dir}")

    async def _run():
        async with async_playwright() as pw:
            for html_path in html_files:
                browser = None
                tmp_dir = None
                try:
                    tmp_dir = Path(tempfile.mkdtemp(dir=video_dir))
                    browser = await pw.chromium.launch()
                    ctx = await browser.new_context(
                        viewport={"width": 1080, "height": 1920},
                        record_video_dir=str(tmp_dir),
                        record_video_size={"width": 1080, "height": 1920},
                    )
                    page = await ctx.new_page()
                    await page.goto(html_path.resolve().as_uri())
                    await page.wait_for_load_state("load")
                    try:
                        await page.wait_for_function(
                            """
                            () => {
                              const img = document.querySelector('img.post-image');
                              if (!img) return false;
                              if (!(img.complete && img.naturalWidth > 0)) return false;
                              const r = img.getBoundingClientRect();
                              const vh = window.innerHeight;
                              const vw = window.innerWidth;
                              const visible = r.width > 10 && r.height > 10 && r.top < vh && r.bottom > 0 && r.left < vw && r.right > 0;
                              return visible;
                            }
                            """,
                            timeout=15000,
                        )
                    except PlaywrightTimeoutError:
                        print(f"[warn] wait_for_function timeout for {html_path.name}, continue recording anyway")
                    await page.wait_for_timeout(hold_ms)
                    target = video_dir / f"{html_path.stem}.webm"
                    await ctx.close()
                    await page.video.save_as(str(target))
                    await browser.close()
                    for f in tmp_dir.iterdir():
                        f.unlink()
                    tmp_dir.rmdir()
                    print(f"[record] {target.name}")
                except Exception as e:
                    print(f"[warn] record_videos failed for {html_path.name}, skip: {e}")
                    if browser is not None:
                        try:
                            await browser.close()
                        except Exception:
                            pass
                    if tmp_dir is not None and tmp_dir.exists():
                        try:
                            for f in tmp_dir.iterdir():
                                f.unlink()
                            tmp_dir.rmdir()
                        except Exception:
                            pass
                    continue

    asyncio.run(_run())


def mux_audio(work_dir: Path, clips: List[Clip]) -> None:
    video_dir = work_dir / "video"
    clips_dir = work_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = resolve_ffmpeg()
    for idx, clip in enumerate(clips, start=1):
        webm = video_dir / f"clip-{idx:02d}.webm"
        if not webm.exists():
            print(f"[warn] missing video for {clip.id}, skip")
            continue
        out = clips_dir / f"clip-{idx:02d}.mp4"
        cmd = [
            ffmpeg_bin,
            "-y",
            "-ss",
            "0.1",
            "-i",
            str(webm),
            "-i",
            str(clip.bg_audio),
            "-t",
            "4",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(out),
        ]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"[warn] ffmpeg failed for {webm.name}, retry once: {e}")
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e2:
                print(f"[warn] ffmpeg failed twice, skip clip: {e2}")
                continue
        print(f"[clip] {out}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Reddit → 3s clips pipeline")
    parser.add_argument(
        "--config",
        default="scripts/reddit_comment2video_config.json",
        help="Config JSON path",
    )
    parser.add_argument(
        "--max-clips",
        type=int,
        default=None,
        help="Max clips to generate (default: config.default_max_clips)",
    )
    parser.add_argument(
        "--work-dir",
        default=None,
        help="Working directory (default: <output_dir>)",
    )
    parser.add_argument(
        "--policy-only",
        action="store_true",
        help="Only run fetch + YouTube policy checks; do not generate videos.",
    )
    args = parser.parse_args(argv)

    cfg_path = ROOT_DIR / args.config
    cfg = load_config(cfg_path)
    safety_filters = load_safety_filters(ROOT_DIR / cfg.get("youtube_safety_filters_path", ""))

    max_clips = args.max_clips if args.max_clips is not None else int(cfg.get("default_max_clips", 2))

    output_root = ROOT_DIR / cfg.get("output_dir", "out/reddit-3s-clips")
    output_root.mkdir(parents=True, exist_ok=True)
    work_dir = Path(args.work_dir) if args.work_dir else output_root

    clips = pick_clips(cfg, safety_filters, max_clips=max_clips)
    if not clips:
        print("No clips selected after filtering.")
        return 0

    if args.policy_only:
        print(f"[policy-only] passed={len(clips)} (would generate up to {max_clips})")
        return 0

    template_path = ROOT_DIR / "public/reddit-3s-template/template.html"
    ensure_images(work_dir, clips)
    if not clips:
        print("No clips left after image download.")
        return 0

    def _clip_to_jsonable(c: Clip) -> dict:
        d = asdict(c)
        out = {}
        for k, v in d.items():
            if k in ("persona", "bg_video", "bg_audio"):
                continue
            if isinstance(v, Path):
                out[k] = str(v)
            else:
                out[k] = v
        out["persona"] = {
            "youtube_channel_id": c.persona.youtube_channel_id,
            "name": c.persona.name,
            "avatar_path": str(c.persona.avatar_path),
        }
        out["bg_video"] = str(c.bg_video)
        out["bg_audio"] = str(c.bg_audio)
        return out

    manifest = {
        "count": len(clips),
        "clips": [_clip_to_jsonable(c) for c in clips],
    }
    (work_dir / "clips_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fill_comments_via_playwright(clips)
    render_html(work_dir, template_path, clips)
    record_videos(work_dir, hold_ms=4000)
    mux_audio(work_dir, clips)

    print(f"Done. Clips in: {work_dir / 'clips'}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

