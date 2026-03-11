#!/usr/bin/env python3
"""
TOS 上传配置：reddit_comment2video 生成结果上传到火山 TOS。

优先从环境变量读取；未设置时使用下方占位（需您替换为真实值后再用上传功能）。
环境变量名：
  REDDIT_COMMENT2VIDEO_TOS_ACCESS_KEY
  REDDIT_COMMENT2VIDEO_TOS_SECRET_KEY
  REDDIT_COMMENT2VIDEO_TOS_ENDPOINT   (例: tos-cn-guangzhou.volces.com)
  REDDIT_COMMENT2VIDEO_TOS_REGION     (例: cn-guangzhou)
  REDDIT_COMMENT2VIDEO_TOS_BUCKET
  REDDIT_COMMENT2VIDEO_TOS_PUBLIC_DOMAIN  (例: https://cdn-video.51sux.com)
"""
from __future__ import annotations

import os

def _env(key: str, default: str = "") -> str:
    return (os.environ.get(key) or default).strip()

TOS_CONFIG = {
    "access_key": _env("REDDIT_COMMENT2VIDEO_TOS_ACCESS_KEY", "请替换为您的 access_key"),
    "secret_key": _env("REDDIT_COMMENT2VIDEO_TOS_SECRET_KEY", "请替换为您的 secret_key"),
    "endpoint": _env("REDDIT_COMMENT2VIDEO_TOS_ENDPOINT", "tos-cn-guangzhou.volces.com"),
    "region": _env("REDDIT_COMMENT2VIDEO_TOS_REGION", "cn-guangzhou"),
    "bucket_name": _env("REDDIT_COMMENT2VIDEO_TOS_BUCKET", "您的 bucket 名"),
    "public_domain": _env("REDDIT_COMMENT2VIDEO_TOS_PUBLIC_DOMAIN", "https://您的公网域名").rstrip("/"),
}
