"""
MCP HTTP 服务：独立端口，通过 query 传 token（?token=xxx）。
Cursor 配置为 "url": "http://host:8001/mcp?token=用户token" 即可，无需 cwd/command/env。
"""
import contextlib

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Mount
from starlette.requests import Request

from .context import set_platform_token
from .server import mcp


def _token_middleware(app):
    """从 query 读取 token 并写入请求上下文，供 client 使用。"""
    async def wrapper(scope, receive, send):
        if scope["type"] != "http":
            await app(scope, receive, send)
            return
        # 仅对 /mcp 或子路径生效，从 query 取 token
        path = scope.get("path", "") or ""
        query_string = scope.get("query_string", b"").decode("utf-8")
        token = None
        if query_string:
            from urllib.parse import parse_qs
            params = parse_qs(query_string)
            tokens = params.get("token") or params.get("api_key")
            if tokens:
                token = (tokens[0] or "").strip() or None
        set_platform_token(token)
        try:
            await app(scope, receive, send)
        finally:
            set_platform_token(None)
    return wrapper


# 使用 session_manager.run() 作为 lifespan，并挂载 MCP streamable HTTP app
@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    async with mcp.session_manager.run():
        yield


# 先包装 MCP app：请求进来时先设 token，再交给 MCP
_raw_mcp_app = mcp.streamable_http_app()
_wrapped_mcp_app = _token_middleware(_raw_mcp_app)

app = Starlette(
    routes=[Mount("/", app=_wrapped_mcp_app)],
    lifespan=lifespan,
)
