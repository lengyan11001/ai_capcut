"""
纯 HTTP 版 MCP Server（不再依赖 FastMCP 的 streamable-http）。

- 端点：/mcp
- 传输：符合 MCP Streamable HTTP 规范的最简实现：
  - 只实现 POST JSON 响应，不实现 SSE（GET /mcp 返回 405）
  - 仅支持 initialize / tools/list / tools/call，其他方法返回 -32601
- 鉴权：从 query 参数 `token`（或 `api_key`）读取平台 JWT，转发到测试平台后端。

Cursor / Claude 等客户端的配置示例：

  "mcpServers": {
    "ai-test-platform": {
      "url": "http://host:8001/mcp?token=用户平台JWT"
    }
  }
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route


BASE_URL = os.environ.get("AI_TEST_PLATFORM_BASE_URL", "http://localhost:8000").rstrip("/")


def _get_token_from_request(request: Request) -> Optional[str]:
    """从 query 或 Header 中解析平台 token。"""
    qp = request.query_params
    token = qp.get("token") or qp.get("api_key")
    if not token:
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip() or None
    return token or None


def _backend_headers(token: Optional[str]) -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _tool_definitions() -> List[Dict[str, Any]]:
    """返回 tools/list 用到的工具定义。"""
    return [
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


async def _call_tool(name: str, args: Dict[str, Any], token: Optional[str]) -> Tuple[List[Dict[str, Any]], bool]:
    """根据工具名调用测试平台后端，返回 (content, is_error)。"""
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
    if isinstance(data, dict) and data.get("detail") and getattr(r, "status_code", 200) >= 400:
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
            "instructions": "调用测试平台 API：单接口测试、从 OpenAPI 文档生成/执行用例、查积分与计费。",
        }
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result,
        }

    if method == "tools/list":
        tools = _tool_definitions()
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
        content, is_error = await _call_tool(name, arguments, token)
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
)
