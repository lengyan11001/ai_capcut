#!/usr/bin/env python3
"""
FastAPI 服务：封装 reddit_to_clips 作为 reddit_comment2video skill 后端。

主要端点：
  POST /generate-clips
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import List, Optional

import tos
from fastapi import FastAPI
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = "scripts/reddit_comment2video_config.json"
TOS_KEY_PREFIX = "reddit-comment2video"


class GenerateRequest(BaseModel):
    max_clips: Optional[int] = None
    subreddits: Optional[List[str]] = None
    work_dir: Optional[str] = None
    config_path: Optional[str] = None


class ClipInfo(BaseModel):
    id: str
    subreddit: str
    title: str
    comment_text: str
    video_path: str
    public_url: Optional[str] = None


class GenerateResponse(BaseModel):
    success: bool
    count: int
    work_dir: str
    clips: List[ClipInfo]
    error: Optional[str] = None


app = FastAPI(title="Reddit Comment2Video Skill")


def _load_config_subreddit_names(config_path: Optional[str] = None) -> List[str]:
    """从配置文件读取已配置的板块名称列表（无 r/ 前缀）。"""
    path = ROOT_DIR / (config_path or DEFAULT_CONFIG)
    if not path.exists():
        return []
    try:
        cfg = json.loads(path.read_text("utf-8"))
        names = []
        for item in cfg.get("subreddits", []):
            n = (item.get("name") or "").strip()
            if n:
                names.append(n)
        return names
    except Exception:
        return []


@app.get("/configured-subreddits", summary="当前已配置的板块列表")
def get_configured_subreddits(config_path: Optional[str] = None) -> dict:
    """返回配置文件中 subreddits 的 name 列表及数量，供平台/会话查询。"""
    names = _load_config_subreddit_names(config_path)
    return {"subreddits": names, "count": len(names)}


def _get_tos_config() -> dict:
    """从环境变量或 upload_latest_clips_to_tos 读取 TOS 配置；缺项则返回空 dict。"""
    # 优先环境变量（部署时推荐）
    ak = os.environ.get("REDDIT_COMMENT2VIDEO_TOS_ACCESS_KEY", "").strip()
    sk = os.environ.get("REDDIT_COMMENT2VIDEO_TOS_SECRET_KEY", "").strip()
    endpoint = os.environ.get("REDDIT_COMMENT2VIDEO_TOS_ENDPOINT", "").strip()
    region = os.environ.get("REDDIT_COMMENT2VIDEO_TOS_REGION", "").strip()
    bucket = os.environ.get("REDDIT_COMMENT2VIDEO_TOS_BUCKET", "").strip()
    public_domain = os.environ.get("REDDIT_COMMENT2VIDEO_TOS_PUBLIC_DOMAIN", "").strip()
    if all([ak, sk, endpoint, region, bucket, public_domain]):
        return {
            "access_key": ak,
            "secret_key": sk,
            "endpoint": endpoint,
            "region": region,
            "bucket_name": bucket,
            "public_domain": public_domain.rstrip("/"),
        }
    tos_config_path = ROOT_DIR / "upload_latest_clips_to_tos.py"
    if not tos_config_path.exists():
        return {}
    scope: dict = {}
    try:
        code = tos_config_path.read_text(encoding="utf-8")
        exec(code, scope, scope)
    except Exception:
        return {}
    cfg = scope.get("TOS_CONFIG")
    if not isinstance(cfg, dict):
        return {}
    return cfg


def _upload_to_tos(clips_dir: Path) -> dict[str, str]:
    urls: dict[str, str] = {}
    cfg = _get_tos_config()
    if not cfg:
        return {}
    ak = cfg.get("access_key")
    sk = cfg.get("secret_key")
    endpoint = cfg.get("endpoint")
    region = cfg.get("region")
    bucket = cfg.get("bucket_name")
    public_domain = (cfg.get("public_domain") or "").rstrip("/")
    if not all([ak, sk, endpoint, region, bucket, public_domain]):
        return {}
    client = tos.TosClientV2(
        ak=ak,
        sk=sk,
        endpoint=endpoint,
        region=region,
        enable_verify_ssl=False,
    )
    for clip in sorted(p for p in clips_dir.glob("clip-0*.mp4") if p.is_file()):
        key = f"{TOS_KEY_PREFIX}/{clip.name}"
        try:
            with clip.open("rb") as f:
                client.put_object(
                    bucket=bucket,
                    key=key,
                    content=f,
                    content_length=clip.stat().st_size,
                )
            urls[clip.name] = f"{public_domain}/{key}"
        except Exception:
            continue
    return urls


def _run_pipeline(req: GenerateRequest) -> GenerateResponse:
    script = ROOT_DIR / "scripts" / "reddit_to_clips.py"
    if not script.exists():
        return GenerateResponse(
            success=False,
            count=0,
            work_dir="",
            clips=[],
            error=f"脚本不存在: {script}",
        )
    config_path = req.config_path or DEFAULT_CONFIG
    args = ["python3", str(script), "--config", config_path]
    if req.max_clips is not None:
        args += ["--max-clips", str(req.max_clips)]
    if req.work_dir:
        work_dir = Path(req.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        args += ["--work-dir", str(work_dir)]
    else:
        work_dir = None

    proc = subprocess.run(args, cwd=str(ROOT_DIR))
    if proc.returncode != 0:
        return GenerateResponse(
            success=False,
            count=0,
            work_dir=str(work_dir or ""),
            clips=[],
            error=f"reddit_to_clips 退出码 {proc.returncode}",
        )

    if work_dir is None:
        cfg_path = ROOT_DIR / config_path
        if not cfg_path.exists():
            return GenerateResponse(
                success=False,
                count=0,
                work_dir="",
                clips=[],
                error=f"找不到配置文件: {cfg_path}",
            )
        cfg = json.loads(cfg_path.read_text("utf-8"))
        output_root = ROOT_DIR / cfg.get("output_dir", "out/reddit-comment2video-clips")
        work_dir = output_root

    manifest_path = work_dir / "clips_manifest.json"
    clips_dir = work_dir / "clips"
    if not manifest_path.exists():
        return GenerateResponse(
            success=False,
            count=0,
            work_dir=str(work_dir),
            clips=[],
            error=f"未找到 clips_manifest.json in {work_dir}",
        )
    manifest = json.loads(manifest_path.read_text("utf-8"))
    clips_raw = manifest.get("clips", [])
    public_url_map = _upload_to_tos(clips_dir)

    clips = []
    for idx, c in enumerate(clips_raw, start=1):
        mp4 = clips_dir / f"clip-{idx:02d}.mp4"
        clips.append(
            ClipInfo(
                id=str(c.get("id", "")),
                subreddit=str(c.get("subreddit", "")),
                title=str(c.get("title", "")),
                comment_text=str(c.get("comment_text", "")),
                video_path=str(mp4),
                public_url=public_url_map.get(mp4.name),
            )
        )
    return GenerateResponse(
        success=True,
        count=len(clips),
        work_dir=str(work_dir),
        clips=clips,
        error=None,
    )


@app.post("/generate-clips", response_model=GenerateResponse)
def generate_clips(req: GenerateRequest) -> GenerateResponse:
    return _run_pipeline(req)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "reddit_skill_server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )
