"""MCP Server：暴露测试平台能力给 Cursor 等 MCP 客户端。"""
import json
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from . import client

mcp = FastMCP(
    name="AI 测试平台",
    instructions="调用测试平台 API：单接口测试、从 OpenAPI 文档生成/执行用例、查积分与计费。需配置 AI_TEST_PLATFORM_BASE_URL 与 AI_TEST_PLATFORM_TOKEN。",
)


@mcp.tool()
def run_api_test(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    query: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
    expect_status: int = 200,
    timeout_seconds: float = 10.0,
) -> str:
    """执行单次 HTTP 接口测试（扣 1 积分）。"""
    payload = {
        "url": url,
        "method": method.upper(),
        "headers": headers or {},
        "query": query or {},
        "body": body,
        "expect_status": expect_status,
        "timeout_seconds": timeout_seconds,
    }
    try:
        data = client.post("/api-test", payload)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except RuntimeError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def generate_cases_from_doc(
    schema_url: Optional[str] = None,
    schema_urls: Optional[List[str]] = None,
    base_url: Optional[str] = None,
    max_cases_per_api: int = 1,
) -> str:
    """仅从 Swagger/OpenAPI 文档生成用例，不执行（不扣费）。传 schema_url 或 schema_urls 之一。"""
    if not schema_url and not schema_urls:
        return json.dumps({"error": "请提供 schema_url 或 schema_urls"}, ensure_ascii=False)
    payload = {
        "only_generate": True,
        "max_cases_per_api": max_cases_per_api,
    }
    if schema_url:
        payload["schema_url"] = schema_url.strip()
    if schema_urls:
        payload["schema_urls"] = [u.strip() for u in schema_urls if u and u.strip()]
    if base_url:
        payload["base_url"] = base_url.strip()
    try:
        data = client.post("/api-test/from-doc", payload)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except RuntimeError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def generate_and_run_from_doc(
    schema_url: Optional[str] = None,
    schema_urls: Optional[List[str]] = None,
    base_url: Optional[str] = None,
    max_cases_per_api: int = 1,
    extra_headers: Optional[Dict[str, str]] = None,
    extra_query: Optional[Dict[str, Any]] = None,
    auth: Optional[Dict[str, Any]] = None,
) -> str:
    """从 Swagger/OpenAPI 文档生成用例并执行（按执行条数扣积分）。传 schema_url 或 schema_urls 之一。可选 auth（login_url、username、password、token_response_path 等）先登录取 token。"""
    if not schema_url and not schema_urls:
        return json.dumps({"error": "请提供 schema_url 或 schema_urls"}, ensure_ascii=False)
    payload = {
        "only_generate": False,
        "max_cases_per_api": max_cases_per_api,
    }
    if schema_url:
        payload["schema_url"] = schema_url.strip()
    if schema_urls:
        payload["schema_urls"] = [u.strip() for u in schema_urls if u and u.strip()]
    if base_url:
        payload["base_url"] = base_url.strip()
    if extra_headers:
        payload["extra_headers"] = extra_headers
    if extra_query:
        payload["extra_query"] = extra_query
    if auth:
        payload["auth"] = auth
    try:
        data = client.post("/api-test/from-doc", payload)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except RuntimeError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def get_me() -> str:
    """查询当前用户信息与剩余积分（需已配置 token）。"""
    try:
        data = client.get("/auth/me")
        return json.dumps(data, ensure_ascii=False, indent=2)
    except RuntimeError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def list_pricing() -> str:
    """查询计费规则（积分单价，公开）。"""
    try:
        data = client.get("/auth/pricing")
        return json.dumps(data, ensure_ascii=False, indent=2)
    except RuntimeError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
