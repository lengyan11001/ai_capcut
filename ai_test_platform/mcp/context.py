"""请求级上下文：HTTP 模式下从 query 取 token，供 client 使用。"""
import contextvars
from typing import Optional

# 当前请求的 platform token（仅 HTTP 模式由 middleware 设置）
_platform_token: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "platform_token", default=None
)


def set_platform_token(token: Optional[str]) -> None:
    _platform_token.set(token)


def get_platform_token() -> Optional[str]:
    try:
        return _platform_token.get()
    except LookupError:
        return None
