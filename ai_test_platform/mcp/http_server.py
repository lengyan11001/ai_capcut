"""
纯 HTTP 版 MCP Server（不再依赖 FastMCP 的 streamable-http）。

- 端点：/mcp
- 传输：符合 MCP Streamable HTTP 规范的最简实现：
  - 只实现 POST JSON 响应，不实现 SSE（GET /mcp 返回 405）
  - 仅支持 initialize / tools/list / tools/call，其他方法返回 -32601
- 鉴权：从 query 参数 `token`（或 `api_key`）读取用户 JWT，转发到控制台后端。

Cursor / Claude 等客户端的配置示例：

  "mcpServers": {
    "ai-test-platform": {
      "url": "http://host:8001/mcp?token=用户JWT"
    }
  }
"""

import json
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route


BASE_URL = os.environ.get("AI_TEST_PLATFORM_BASE_URL", "http://localhost:8000").rstrip("/")
AI_TEST_PLATFORM_ADMIN_TOKEN = os.environ.get("AI_TEST_PLATFORM_ADMIN_TOKEN", "").strip()
AI_TEST_PLATFORM_X_ADMIN_TOKEN = os.environ.get("AI_TEST_PLATFORM_X_ADMIN_TOKEN", "").strip()
CAPABILITY_SUTUI_MCP_URL = os.environ.get("CAPABILITY_SUTUI_MCP_URL", "").strip()
_allowlist_raw = os.environ.get("CAPABILITY_ALLOWLIST", "").strip()
CAPABILITY_ALLOWLIST = {x.strip() for x in _allowlist_raw.split(",") if x.strip()}
CAPABILITY_CATALOG_PATH = os.environ.get("CAPABILITY_CATALOG_PATH", "").strip()
CAPABILITY_UPSTREAM_URLS_JSON = os.environ.get("CAPABILITY_UPSTREAM_URLS_JSON", "").strip()
CAPABILITY_IMAGE_DEFAULT_MODEL = os.environ.get("CAPABILITY_IMAGE_DEFAULT_MODEL", "jimeng-4.0").strip()
ADMIN_ONLY_CAPABILITIES = {"sutui.account"}

DEFAULT_CAPABILITY_CATALOG: Dict[str, Dict[str, Any]] = {
    "image.generate": {
        "description": "生成图片（统一能力入口）",
        "upstream": "sutui",
        "upstream_tool": "generate",
        "enabled": True,
        "is_default": True,
        "arg_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "生成提示词"},
                "model": {"type": "string", "description": "可选，模型名"},
                "size": {"type": "string", "description": "可选，图像尺寸"},
            },
            "required": ["prompt"],
        },
    },
    "task.get_result": {
        "description": "查询任务结果（统一能力入口）",
        "upstream": "sutui",
        "upstream_tool": "get_result",
        "enabled": True,
        "is_default": True,
        "arg_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "任务 ID"},
            },
            "required": ["task_id"],
        },
    },
}


def _load_catalog_from_file(path: Path) -> Dict[str, Dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("capability catalog file must be object")
    out: Dict[str, Dict[str, Any]] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, dict):
            out[k] = v
    return out


def _load_capability_catalog() -> Dict[str, Dict[str, Any]]:
    """
    能力目录优先级：
    1) CAPABILITY_CATALOG_PATH 指向的 JSON 文件
    2) 项目内本地覆盖文件 mcp/capability_catalog.local.json（建议运维改这个）
    3) 项目内默认文件 mcp/capability_catalog.json
    4) 代码默认 DEFAULT_CAPABILITY_CATALOG
    """
    # 显式路径优先
    if CAPABILITY_CATALOG_PATH:
        try:
            p = Path(CAPABILITY_CATALOG_PATH)
            if p.exists():
                return _load_catalog_from_file(p)
        except Exception:
            pass
    # 项目默认配置文件
    try:
        # 本地覆盖文件（建议放本机配置，不纳入 git）
        p_local = Path(__file__).resolve().parent / "capability_catalog.local.json"
        if p_local.exists():
            return _load_catalog_from_file(p_local)
    except Exception:
        pass
    try:
        p = Path(__file__).resolve().parent / "capability_catalog.json"
        if p.exists():
            return _load_catalog_from_file(p)
    except Exception:
        pass
    return DEFAULT_CAPABILITY_CATALOG


CAPABILITY_CATALOG = _load_capability_catalog()


def _load_upstream_urls() -> Dict[str, str]:
    """
    上游 URL 映射：
    - CAPABILITY_UPSTREAM_URLS_JSON: {"sutui":"https://..."}
    - 向后兼容 CAPABILITY_SUTUI_MCP_URL
    """
    urls: Dict[str, str] = {}
    if CAPABILITY_UPSTREAM_URLS_JSON:
        try:
            parsed = json.loads(CAPABILITY_UPSTREAM_URLS_JSON)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    if isinstance(k, str) and isinstance(v, str) and v.strip():
                        urls[k.strip()] = v.strip()
        except Exception:
            pass
    if "sutui" not in urls and CAPABILITY_SUTUI_MCP_URL:
        urls["sutui"] = CAPABILITY_SUTUI_MCP_URL
    return urls


CAPABILITY_UPSTREAM_URLS = _load_upstream_urls()


def _enabled_capability_ids() -> List[str]:
    out: List[str] = []
    for cid, cfg in CAPABILITY_CATALOG.items():
        if CAPABILITY_ALLOWLIST and cid not in CAPABILITY_ALLOWLIST:
            continue
        if cfg.get("enabled") is False:
            continue
        out.append(cid)
    return sorted(out)


async def _fetch_backend_available_capabilities(token: Optional[str]) -> Optional[Dict[str, Dict[str, Any]]]:
    """从后端读取当前用户可用能力；失败时返回 None（由调用方回退本地目录）。"""
    if not token:
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(f"{BASE_URL}/capabilities/available", headers=_backend_headers(token))
        if r.status_code != 200:
            return None
        data = r.json()
        arr = data.get("capabilities") if isinstance(data, dict) else None
        if not isinstance(arr, list):
            return None
        out: Dict[str, Dict[str, Any]] = {}
        for x in arr:
            if not isinstance(x, dict):
                continue
            cid = str(x.get("capability_id") or "").strip()
            if not cid:
                continue
            out[cid] = {
                "description": str(x.get("description") or cid),
                "upstream": str(x.get("upstream") or "sutui"),
                "upstream_tool": str(x.get("upstream_tool") or "").strip(),
                "arg_schema": x.get("arg_schema") if isinstance(x.get("arg_schema"), dict) else {"type": "object", "properties": {}},
                "unit_credits": int(x.get("unit_credits") or 0),
                "enabled": True,
            }
        return out
    except Exception:
        return None


def _extract_user_id_from_request(request: Request) -> Optional[int]:
    """
    尝试从请求上下文解析 user_id。
    兼容 query 与常见 header，尤其 OpenClaw 的 agent_id（如 user_12）。
    """
    qp = request.query_params
    q_user_id = (qp.get("user_id") or "").strip()
    if q_user_id.isdigit():
        return int(q_user_id)
    candidates = [
        request.headers.get("x-openclaw-agent-id") or "",
        request.headers.get("openclaw-agent-id") or "",
        request.headers.get("x-agent-id") or "",
        request.headers.get("x-user-id") or "",
    ]
    for raw in candidates:
        v = str(raw or "").strip()
        if not v:
            continue
        if v.isdigit():
            return int(v)
        m = re.search(r"user[_-]?(\d+)$", v, flags=re.I)
        if m:
            return int(m.group(1))
    return None


async def _fetch_backend_capabilities_by_user_id(user_id: int) -> Optional[Dict[str, Dict[str, Any]]]:
    """
    当调用链未透传用户 token 时，用管理员 token 按 user_id 读取能力（避免退化到本地默认目录）。
    依赖 AI_TEST_PLATFORM_ADMIN_TOKEN（可回退 AI_TEST_PLATFORM_TOKEN）。
    """
    admin_token = AI_TEST_PLATFORM_ADMIN_TOKEN or (os.environ.get("AI_TEST_PLATFORM_TOKEN") or "").strip()
    x_admin_token = AI_TEST_PLATFORM_X_ADMIN_TOKEN or ""
    try:
        registry = None
        policies = None

        # 优先使用固定管理密钥（X-Admin-Token），避免 Bearer JWT 过期导致能力列表为空。
        if x_admin_token:
            async with httpx.AsyncClient(timeout=20.0) as client:
                h = {"Content-Type": "application/json", "X-Admin-Token": x_admin_token}
                r_registry = await client.get(f"{BASE_URL}/capabilities/registry", headers=h)
                r_policies = await client.get(f"{BASE_URL}/capabilities/policies", headers=h)
            if r_registry.status_code == 200 and r_policies.status_code == 200:
                registry = r_registry.json()
                policies = r_policies.json()

        # 次选 Bearer 管理员 token（兼容旧配置）。
        if (registry is None or policies is None) and admin_token:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r_registry = await client.get(
                    f"{BASE_URL}/capabilities/admin/registry",
                    headers=_backend_headers(admin_token),
                )
                r_policies = await client.get(
                    f"{BASE_URL}/capabilities/admin/policies?user_id={int(user_id)}",
                    headers=_backend_headers(admin_token),
                )
            if r_registry.status_code == 200 and r_policies.status_code == 200:
                registry = r_registry.json()
                policies = r_policies.json()

        if registry is None or policies is None:
            return None

        if not isinstance(registry, list) or not isinstance(policies, list):
            return None

        reg_map: Dict[str, Dict[str, Any]] = {}
        for row in registry:
            if not isinstance(row, dict):
                continue
            cid = str(row.get("capability_id") or "").strip()
            if not cid or row.get("enabled") is False:
                continue
            reg_map[cid] = {
                "description": str(row.get("description") or cid),
                "upstream": str(row.get("upstream") or "sutui"),
                "upstream_tool": str(row.get("upstream_tool") or "").strip(),
                "arg_schema": row.get("arg_schema") if isinstance(row.get("arg_schema"), dict) else {"type": "object", "properties": {}},
                "unit_credits": int(row.get("unit_credits") or 0),
                "enabled": True,
            }

        allow_set: set[str] = set()
        deny_set: set[str] = set()
        has_any_user_policy = False
        for p in policies:
            if not isinstance(p, dict):
                continue
            if not p.get("enabled"):
                continue
            st = str(p.get("subject_type") or "").strip().lower()
            sv = str(p.get("subject_value") or "").strip()
            if st != "user_id" or sv != str(int(user_id)):
                continue
            has_any_user_policy = True
            cid = str(p.get("capability_id") or "").strip()
            if not cid:
                continue
            effect = str(p.get("effect") or "allow").strip().lower()
            if effect == "deny":
                deny_set.add(cid)
            else:
                allow_set.add(cid)

        out: Dict[str, Dict[str, Any]] = {}
        # 无法确认用户管理员身份时，保守处理：隐藏 admin-only 能力，避免普通用户旁路获取。
        is_admin_user = False
        if admin_token:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    r_users = await client.get(
                        f"{BASE_URL}/auth/admin/users",
                        headers=_backend_headers(admin_token),
                    )
                if r_users.status_code == 200:
                    users = r_users.json()
                    if isinstance(users, list):
                        for u in users:
                            if not isinstance(u, dict):
                                continue
                            if int(u.get("id") or 0) == int(user_id):
                                role = str(u.get("role") or "").strip().lower()
                                is_admin_user = role == "admin"
                                break
            except Exception:
                is_admin_user = False
        if has_any_user_policy:
            for cid in sorted(allow_set):
                if cid in deny_set:
                    continue
                if cid in reg_map:
                    if cid in ADMIN_ONLY_CAPABILITIES and not is_admin_user:
                        continue
                    out[cid] = reg_map[cid]
            return out
        # 无策略时保持兼容：返回全部启用能力
        if not is_admin_user:
            for c in ADMIN_ONLY_CAPABILITIES:
                reg_map.pop(c, None)
        return reg_map
    except Exception:
        return None


async def _runtime_catalog(token: Optional[str], request: Optional[Request] = None) -> Dict[str, Dict[str, Any]]:
    backend_catalog = await _fetch_backend_available_capabilities(token)
    if backend_catalog is not None:
        return backend_catalog
    if request is not None:
        uid = _extract_user_id_from_request(request)
        if uid:
            by_user_catalog = await _fetch_backend_capabilities_by_user_id(uid)
            if by_user_catalog is not None:
                return by_user_catalog
    # 兜底回退本地目录，避免 tools/list 为空导致会话层完全不触发能力。
    out: Dict[str, Dict[str, Any]] = {}
    for cid in _enabled_capability_ids():
        out[cid] = CAPABILITY_CATALOG[cid]
    return out


def _truncate_payload_for_audit(value: Any) -> Any:
    """审计入库前裁剪，避免超大 payload。"""
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            out[str(k)] = _truncate_payload_for_audit(v)
        return out
    if isinstance(value, list):
        return [_truncate_payload_for_audit(x) for x in value[:20]]
    if isinstance(value, str):
        return value[:500]
    return value


async def _record_capability_call(
    token: Optional[str],
    capability_id: str,
    success: bool,
    latency_ms: Optional[int],
    request_payload: Dict[str, Any],
    response_payload: Optional[Dict[str, Any]],
    error_message: Optional[str],
    should_charge: bool = True,
    actual_credits: Optional[int] = None,
    source: str = "mcp_invoke",
    chat_session_id: Optional[str] = None,
    chat_context_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """写入后端审计并按能力规则扣费。"""
    if not token:
        return None
    body = {
        "capability_id": capability_id,
        "success": success,
        "latency_ms": latency_ms,
        "request_payload": _redact_sensitive(_truncate_payload_for_audit(request_payload or {})),
        "response_payload": _redact_sensitive(_truncate_payload_for_audit(response_payload or {})),
        "error_message": (error_message or "")[:1000] or None,
        "should_charge": bool(should_charge),
        "actual_credits": actual_credits if isinstance(actual_credits, int) and actual_credits >= 0 else None,
        "source": source,
        "chat_session_id": (chat_session_id or "")[:128] or None,
        "chat_context_id": (chat_context_id or "")[:128] or None,
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(f"{BASE_URL}/capabilities/record-call", json=body, headers=_backend_headers(token))
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


def _get_token_from_request(request: Request) -> Optional[str]:
    """从 query 或 Header 中解析平台 token。"""
    qp = request.query_params
    token = qp.get("token") or qp.get("api_key")
    if not token:
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip() or None
    if not token:
        # 后端 chat -> OpenClaw 显式透传的用户 token（优先恢复真实用户身份）
        user_auth = request.headers.get("x-user-authorization") or ""
        if user_auth.lower().startswith("bearer "):
            token = user_auth[7:].strip() or None
    if not token:
        # 兼容纯 token 透传头
        user_token = (request.headers.get("x-user-token") or "").strip()
        token = user_token or None
    return token or None


def _backend_headers(token: Optional[str]) -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _tool_definitions(catalog: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """返回 tools/list 用到的工具定义。"""
    base_tools = [
        {
            "name": "run_api_test",
            "description": "执行单次 HTTP 接口测试（扣 1 积分）",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "完整接口地址"},
                    "method": {"type": "string", "description": "HTTP 方法，GET/POST 等"},
                    "headers": {"type": "object", "description": "请求头，键值对"},
                    "query": {"type": "object", "description": "Query 参数"},
                    "body": {"description": "请求体 JSON"},
                    "expect_status": {
                        "type": "integer",
                        "description": "期望状态码，默认 200",
                    },
                    "timeout_seconds": {
                        "type": "number",
                        "description": "超时时间（秒），默认 10",
                    },
                },
                "required": ["url"],
            },
        },
        {
            "name": "generate_cases_from_doc",
            "description": "从 Swagger/OpenAPI 文档生成用例，不执行（不扣费，可选仅预估大模型成本）",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "schema_url": {
                        "type": "string",
                        "description": "单个文档地址（schema_url 与 schema_urls 需至少传一个）",
                    },
                    "schema_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "多个文档地址",
                    },
                    "base_url": {
                        "type": "string",
                        "description": "接口统一 base_url，可选",
                    },
                    "max_cases_per_api": {
                        "type": "integer",
                        "description": "每个接口生成多少条用例，默认 1",
                    },
                    "llm_model_id": {
                        "type": "string",
                        "description": "可选：指定用于丰富用例描述的大模型 ID（例如 aliyun:qwen-turbo），不填则不使用大模型",
                    },
                    "estimate_only": {
                        "type": "boolean",
                        "description": "若为 true，仅预估使用该模型的大致积分，不实际调用模型与执行接口",
                    },
                },
            },
        },
        {
            "name": "generate_and_run_from_doc",
            "description": "从文档生成用例并执行（按执行条数 + 可选大模型积分扣费）",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "schema_url": {
                        "type": "string",
                        "description": "单个文档地址（schema_url 与 schema_urls 需至少传一个）",
                    },
                    "schema_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "多个文档地址",
                    },
                    "base_url": {
                        "type": "string",
                        "description": "接口统一 base_url，可选",
                    },
                    "max_cases_per_api": {
                        "type": "integer",
                        "description": "每个接口生成多少条用例，默认 1",
                    },
                    "extra_headers": {
                        "type": "object",
                        "description": "所有请求都会带上的额外 Header，例如固定 Token / API-Key",
                    },
                    "extra_query": {
                        "type": "object",
                        "description": "所有请求都会带上的额外 Query 参数",
                    },
                    "auth": {
                        "type": "object",
                        "description": "可选：先调登录接口取 token 再执行用例的配置",
                    },
                    "llm_model_id": {
                        "type": "string",
                        "description": "可选：指定用于生成更详细用例说明的大模型 ID，例如 aliyun:qwen-plus / volc:doubao-flash / deepseek:chat",
                    },
                    "estimate_only": {
                        "type": "boolean",
                        "description": "若为 true，仅预估执行与大模型的大致积分，不真正调用与扣费",
                    },
                },
            },
        },
        {
            "name": "get_me",
            "description": "查询当前用户信息与剩余积分",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "list_pricing",
            "description": "查询计费规则（积分单价）",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]
    capability_list = sorted(catalog.keys())
    base_tools.extend(
        [
            {
                "name": "list_capabilities",
                "description": "列出平台统一能力白名单（白标能力）",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "invoke_capability",
                "description": "调用平台统一能力路由（不暴露供应商细节）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "capability_id": {
                            "type": "string",
                            "enum": capability_list,
                            "description": "能力 ID（仅白名单可用）",
                        },
                        "payload": {
                            "type": "object",
                            "description": "能力调用参数",
                        },
                    },
                    "required": ["capability_id", "payload"],
                },
            },
        ]
    )
    return base_tools


def _redact_sensitive(value: Any) -> Any:
    """对上游响应做兜底脱敏，避免账户/积分/API key 等信息透传。"""
    blocked_keys = {"api_key", "apikey", "token", "balance", "points", "credits", "account", "account_id", "uid", "user_id"}
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            key_lower = str(k).lower()
            if key_lower in blocked_keys:
                continue
            out[k] = _redact_sensitive(v)
        return out
    if isinstance(value, list):
        return [_redact_sensitive(x) for x in value]
    if isinstance(value, str):
        redacted = re.sub(r"(sk-[A-Za-z0-9]{10,})", "[REDACTED_KEY]", value)
        redacted = re.sub(r"(api[_-]?key\s*[:=]\s*)([^\s,]+)", r"\1[REDACTED]", redacted, flags=re.I)
        return redacted
    return value


def _extract_actual_credits(value: Any) -> Optional[int]:
    """从上游响应里提取实际积分消耗（若上游返回）。"""
    if isinstance(value, dict):
        # 常见命名：credits_charged / cost_credits / charged_credits
        for key in ("credits_charged", "cost_credits", "charged_credits", "actual_credits"):
            v = value.get(key)
            if isinstance(v, (int, float)) and v > 0:
                return int(v)
        for _, v in value.items():
            found = _extract_actual_credits(v)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _extract_actual_credits(item)
            if found is not None:
                return found
    return None


def _extract_should_charge(value: Any) -> bool:
    """从上游响应里提取是否应计费；未显式返回时默认免费（False）。"""
    if isinstance(value, dict):
        for key in ("should_charge", "charged", "cost_incurred", "has_cost"):
            if key in value:
                v = value.get(key)
                if isinstance(v, bool):
                    return v
                if isinstance(v, (int, float)):
                    return v > 0
                if isinstance(v, str):
                    return v.strip().lower() in ("1", "true", "yes", "charged")
        # 若直接给出实际费用，则视为应扣费
        cost = _extract_actual_credits(value)
        if cost is not None and cost > 0:
            return True
    return False


def _extract_upstream_nested_error(value: Any) -> str:
    """
    解析上游 MCP 常见嵌套响应中的错误文本。
    场景：result.content[0].text 是 JSON 字符串，包含 {"success": false, "error": "..."}。
    """
    if not isinstance(value, dict):
        return ""
    top_error = value.get("error")
    if isinstance(top_error, dict):
        return str(top_error.get("message") or "")[:500]
    result = value.get("result")
    if not isinstance(result, dict):
        return ""
    content = result.get("content")
    if not isinstance(content, list) or not content:
        return ""
    first = content[0]
    if not isinstance(first, dict):
        return ""
    text = first.get("text")
    if not isinstance(text, str) or not text.strip():
        return ""
    try:
        inner = json.loads(text)
        if isinstance(inner, dict):
            if inner.get("success") is False and inner.get("error"):
                return str(inner.get("error"))[:500]
    except Exception:
        return ""
    return ""


async def _call_upstream_mcp_tool(server_url: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    调用上游 MCP HTTP 工具：
    - 先 initialize（兼容部分要求初始化的服务）
    - 再 tools/call
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        init_body = {
            "jsonrpc": "2.0",
            "id": "init-capability",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "ai-test-platform-capability-proxy", "version": "0.1.0"},
            },
        }
        init_resp = await client.post(server_url, json=init_body)
        session_id = (
            init_resp.headers.get("Mcp-Session-Id")
            or init_resp.headers.get("mcp-session-id")
            or ""
        )
        if not session_id:
            try:
                init_json = init_resp.json()
                if isinstance(init_json, dict):
                    result = init_json.get("result") or {}
                    if isinstance(result, dict):
                        session_id = str(result.get("sessionId") or result.get("session_id") or "").strip()
            except Exception:
                session_id = ""
        call_body = {
            "jsonrpc": "2.0",
            "id": "call-capability",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        call_headers = {"Mcp-Session-Id": session_id} if session_id else {}
        r = await client.post(server_url, json=call_body, headers=call_headers)
        try:
            return r.json()
        except Exception:
            return {"error": {"message": f"Upstream MCP 返回非 JSON: status={r.status_code}"}}


async def _call_tool(name: str, args: Dict[str, Any], token: Optional[str], request: Optional[Request] = None) -> Tuple[List[Dict[str, Any]], bool]:
    """根据工具名调用控制台后端，返回 (content, is_error)。"""
    r: Optional[httpx.Response] = None
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if name == "run_api_test":
                payload = {
                    "url": args.get("url"),
                    "method": (args.get("method") or "GET").upper(),
                    "headers": args.get("headers") or {},
                    "query": args.get("query") or {},
                    "body": args.get("body"),
                    "expect_status": args.get("expect_status", 200),
                    "timeout_seconds": float(args.get("timeout_seconds", 10.0)),
                }
                r = await client.post(f"{BASE_URL}/api-test", json=payload, headers=_backend_headers(token))
                data = r.json()
            elif name in ("generate_cases_from_doc", "generate_and_run_from_doc"):
                only_generate = name == "generate_cases_from_doc"
                payload: Dict[str, Any] = {
                    "only_generate": only_generate,
                    "max_cases_per_api": args.get("max_cases_per_api", 1),
                }
                schema_url = args.get("schema_url")
                schema_urls = args.get("schema_urls")
                if schema_url:
                    payload["schema_url"] = schema_url
                if schema_urls:
                    payload["schema_urls"] = schema_urls
                base_url = args.get("base_url")
                if base_url:
                    payload["base_url"] = base_url
                # MCP 侧可选传入 estimate_only：仅做积分预估
                if "estimate_only" in args:
                    payload["estimate_only"] = bool(args.get("estimate_only"))
                # MCP 侧可选传入 llm_model_id：指定具体大模型计费
                if args.get("llm_model_id"):
                    payload["llm_model_id"] = args["llm_model_id"]
                if args.get("extra_headers"):
                    payload["extra_headers"] = args["extra_headers"]
                if args.get("extra_query"):
                    payload["extra_query"] = args["extra_query"]
                if args.get("auth"):
                    payload["auth"] = args["auth"]
                r = await client.post(f"{BASE_URL}/api-test/from-doc", json=payload, headers=_backend_headers(token))
                data = r.json()
            elif name == "get_me":
                r = await client.get(f"{BASE_URL}/auth/me", headers=_backend_headers(token))
                data = r.json()
            elif name == "list_pricing":
                r = await client.get(f"{BASE_URL}/auth/pricing", headers=_backend_headers(token))
                data = r.json()
            elif name == "list_capabilities":
                catalog = await _runtime_catalog(token, request=request)
                data = {
                    "capabilities": [
                        {
                            "capability_id": cid,
                            "description": catalog[cid].get("description") or cid,
                        }
                        for cid in sorted(catalog.keys())
                    ]
                }
            elif name == "invoke_capability":
                catalog = await _runtime_catalog(token, request=request)
                capability_id = (args.get("capability_id") or "").strip()
                payload = args.get("payload") or {}
                if not isinstance(payload, dict):
                    payload = {}
                if not token:
                    return ([{"type": "text", "text": "缺少用户 token，无法调用能力。请检查 OpenClaw/Gateway 是否透传 Authorization。"}], True)
                if not capability_id:
                    return ([{"type": "text", "text": "capability_id 不能为空"}], True)
                if capability_id not in catalog:
                    return ([{"type": "text", "text": f"能力未开放: {capability_id}"}], True)
                cfg = catalog.get(capability_id)
                if not cfg:
                    return ([{"type": "text", "text": f"未知能力: {capability_id}"}], True)
                upstream_tool = str(cfg.get("upstream_tool") or "").strip()
                if not upstream_tool:
                    return ([{"type": "text", "text": f"能力配置缺失 upstream_tool: {capability_id}"}], True)
                upstream_name = str(cfg.get("upstream") or "sutui").strip()
                upstream_url = CAPABILITY_UPSTREAM_URLS.get(upstream_name, "").strip()
                if not upstream_url:
                    return ([{"type": "text", "text": f"未配置能力上游网关: {upstream_name}"}], True)
                required_credits = int(cfg.get("unit_credits") or 0)
                if required_credits > 0 and token:
                    me = await client.get(f"{BASE_URL}/auth/me", headers=_backend_headers(token))
                    if me.status_code == 200:
                        me_json = me.json() if me.content else {}
                        left = int((me_json or {}).get("credits") or 0)
                        if left < required_credits:
                            return ([{"type": "text", "text": f"积分不足，调用该能力需 {required_credits}，当前 {left}"}], True)
                # 用户通常不会主动提供 model，这里给图片生成补默认模型兜底。
                effective_payload = dict(payload)
                auto_selected_model = ""
                if capability_id == "image.generate" and not str(effective_payload.get("model") or "").strip():
                    if CAPABILITY_IMAGE_DEFAULT_MODEL:
                        effective_payload["model"] = CAPABILITY_IMAGE_DEFAULT_MODEL
                        auto_selected_model = CAPABILITY_IMAGE_DEFAULT_MODEL
                t0 = time.perf_counter()
                upstream_resp = await _call_upstream_mcp_tool(
                    upstream_url,
                    upstream_tool,
                    effective_payload,
                )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                upstream_error = _extract_upstream_nested_error(upstream_resp)
                if not upstream_error and isinstance(upstream_resp, dict) and isinstance(upstream_resp.get("error"), dict):
                    upstream_error = str((upstream_resp.get("error") or {}).get("message") or "")[:500]
                # 若仍返回“缺少 model”，再自动补一次兜底模型重试（兼容上游严格校验）。
                if (
                    capability_id == "image.generate"
                    and upstream_error
                    and ("缺少 model" in upstream_error.lower() or "missing model" in upstream_error.lower() or "缺少 model 参数" in upstream_error)
                    and CAPABILITY_IMAGE_DEFAULT_MODEL
                    and str(effective_payload.get("model") or "").strip() != CAPABILITY_IMAGE_DEFAULT_MODEL
                ):
                    effective_payload["model"] = CAPABILITY_IMAGE_DEFAULT_MODEL
                    auto_selected_model = CAPABILITY_IMAGE_DEFAULT_MODEL
                    t1 = time.perf_counter()
                    upstream_resp = await _call_upstream_mcp_tool(
                        upstream_url,
                        upstream_tool,
                        effective_payload,
                    )
                    latency_ms += int((time.perf_counter() - t1) * 1000)
                    upstream_error = _extract_upstream_nested_error(upstream_resp)
                    if not upstream_error and isinstance(upstream_resp, dict) and isinstance(upstream_resp.get("error"), dict):
                        upstream_error = str((upstream_resp.get("error") or {}).get("message") or "")[:500]
                actual_credits = _extract_actual_credits(upstream_resp)
                should_charge = _extract_should_charge(upstream_resp)
                await _record_capability_call(
                    token=token,
                    capability_id=capability_id,
                    success=not bool(upstream_error),
                    latency_ms=latency_ms,
                    request_payload=effective_payload,
                    response_payload=upstream_resp if isinstance(upstream_resp, dict) else {"raw": str(upstream_resp)},
                    error_message=upstream_error or None,
                    should_charge=should_charge,
                    actual_credits=actual_credits,
                    source="mcp_invoke",
                    chat_context_id=capability_id,
                )
                data = {
                    "capability_id": capability_id,
                    "meta": {"auto_selected_model": auto_selected_model} if auto_selected_model else {},
                    "result": _redact_sensitive(upstream_resp),
                }
            else:
                return (
                    [
                        {
                            "type": "text",
                            "text": f"Unknown tool: {name}",
                        }
                    ],
                    True,
                )
    except Exception as e:  # noqa: BLE001
        return (
            [
                {
                    "type": "text",
                    "text": f"调用后端出错: {e}",
                }
            ],
            True,
        )

    # 如果后端返回 detail 且 HTTP 非 2xx，可以视为错误
    is_error = False
    status_code = getattr(r, "status_code", 200) if r is not None else 200
    if isinstance(data, dict) and data.get("detail") and status_code >= 400:
        is_error = True
        text = json.dumps(data, ensure_ascii=False, indent=2)
    elif (
        isinstance(data, dict)
        and isinstance(data.get("result"), dict)
        and isinstance((data.get("result") or {}).get("error"), dict)
    ):
        is_error = True
        text = json.dumps(data, ensure_ascii=False, indent=2)
    else:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    return [{"type": "text", "text": text}], is_error


def _make_error(id_value: Any, code: int, message: str) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": id_value,
        "error": {
            "code": code,
            "message": message,
        },
    }


async def _handle_single_message(msg: Dict[str, Any], request: Request) -> Optional[Dict[str, Any]]:
    """处理单条 JSON-RPC 消息。通知（无 id）返回 None。"""
    if not isinstance(msg, dict):
        return _make_error(None, -32600, "Invalid JSON-RPC message")

    method = msg.get("method")
    msg_id = msg.get("id")

    # notifications（如 notifications/initialized）无 id，不需要响应
    if msg_id is None:
        return None

    params = msg.get("params") or {}

    if method == "initialize":
        result = {
            "protocolVersion": "2025-03-26",
            "capabilities": {
                "tools": {
                    "listChanged": False,
                }
            },
            "serverInfo": {
                "name": "ai-test-platform-http-mcp",
                "version": "0.1.0",
            },
            "instructions": "调用控制台 API：API 测试、从 OpenAPI 文档生成/执行用例、查积分与计费。",
        }
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result,
        }

    if method == "tools/list":
        token = _get_token_from_request(request)
        catalog = await _runtime_catalog(token, request=request)
        tools = _tool_definitions(catalog)
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": tools
            },
        }

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        token = _get_token_from_request(request)
        content, is_error = await _call_tool(name, arguments, token, request=request)
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": content,
                "isError": is_error,
            },
        }

    # 未实现的方法
    return _make_error(msg_id, -32601, f"Method not found: {method}")


async def mcp_endpoint(request: Request) -> Response:
    """单个 MCP 端点，实现 Streamable HTTP 的最小子集。"""
    if request.method == "GET":
        # 不实现 SSE，按规范返回 405 即可
        return PlainTextResponse("SSE not implemented", status_code=405)

    if request.method != "POST":
        return PlainTextResponse("Method not allowed", status_code=405)

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    # 批处理或单条
    responses: List[Dict[str, Any]] = []

    if isinstance(payload, list):
        for item in payload:
            resp = await _handle_single_message(item, request)
            if resp is not None:
                responses.append(resp)
    elif isinstance(payload, dict):
        resp = await _handle_single_message(payload, request)
        if resp is not None:
            responses.append(resp)
    else:
        return JSONResponse({"error": "Invalid JSON-RPC payload"}, status_code=400)

    if not responses:
        # 纯通知，按规范返回 202 无 body
        return Response(status_code=202)
    if len(responses) == 1:
        return JSONResponse(responses[0])
    return JSONResponse(responses)


app = Starlette(
    routes=[Route("/mcp", mcp_endpoint, methods=["GET", "POST"])],
    middleware=[
        # 允许 localhost / 127.0.0.1 等，避免 OpenClaw 等同机访问时触发 Invalid Host header
        Middleware(TrustedHostMiddleware, allowed_hosts=["*"]),
    ],
)
