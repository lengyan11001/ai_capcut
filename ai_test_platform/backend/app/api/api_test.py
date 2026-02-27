import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import httpx
import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.credits import credits_for_api_test, credits_for_from_doc
from ..db import get_db
from ..models import User
from .auth import get_current_user


router = APIRouter()


class ApiTestRequest(BaseModel):
    url: str = Field(..., description="接口地址，例如：https://httpbin.org/post")
    method: str = Field(
        "GET",
        description="HTTP 方法，大写，例如：GET/POST/PUT/DELETE",
    )
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="可选，请求头",
    )
    query: Dict[str, Any] = Field(
        default_factory=dict,
        description="可选，URL 查询参数",
    )
    body: Optional[Dict[str, Any]] = Field(
        default=None,
        description="可选，JSON 请求体（仅对 POST/PUT/PATCH 有效）",
    )
    expect_status: int = Field(
        200,
        description="期望的 HTTP 状态码，用于简单断言",
    )
    timeout_seconds: float = Field(
        10.0,
        description="超时时间（秒）",
    )


class ApiTestResult(BaseModel):
    passed: bool
    status_code: int
    expect_status: int
    duration_ms: float
    response_headers: Dict[str, str]
    response_snippet: str
    error: Optional[str] = None


class GeneratedTestCase(BaseModel):
    """
    从接口文档自动生成的单条测试用例，含参数设计（query/body 等）
    """

    name: str
    method: str
    path: str
    full_url: str
    description: Optional[str] = None
    expect_status: int = 200
    query: Optional[Dict[str, Any]] = None
    body: Optional[Dict[str, Any]] = None


class AuthConfig(BaseModel):
    """执行前先调用登录接口，取 token 注入到后续请求的 Header"""
    login_url: str = Field(..., description="登录接口完整 URL")
    method: str = Field("POST", description="登录请求方法")
    username: Optional[str] = Field(None, description="登录账号（表单或 JSON 字段名由 body 指定）")
    password: Optional[str] = Field(None, description="登录密码")
    body: Optional[Dict[str, Any]] = Field(
        None,
        description="登录请求体（JSON）。不填且提供 username/password 时按 form 提交",
    )
    token_response_path: str = Field(
        "access_token",
        description="响应中 token 的路径，如 access_token 或 data.token",
    )
    header_name: str = Field("Authorization", description="注入的 Header 名")
    header_prefix: str = Field("Bearer ", description="Header 值前缀，如 Bearer ")


class ApiFromDocRequest(BaseModel):
    schema_url: Optional[str] = Field(
        None,
        description="单个接口文档地址（与 schema_urls 二选一）",
    )
    schema_urls: Optional[List[str]] = Field(
        None,
        description="多个接口文档地址，每行一个；与 schema_url 二选一，会合并所有文档的接口后一起生成/执行",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="可选，实际测试环境基础地址，例如：https://api.example.com",
    )
    max_cases_per_api: int = Field(
        1,
        ge=1,
        le=5,
        description="每个接口最多生成的用例数（当前 V1 仅生成 1 条）",
    )
    only_generate: bool = Field(
        False,
        description="为 true 时只生成用例不执行",
    )
    extra_headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="所有请求都会带上的额外 Header（如 API-Key、固定 Token）",
    )
    extra_query: Optional[Dict[str, Any]] = Field(
        default=None,
        description="所有请求都会带上的额外查询参数",
    )
    auth: Optional[AuthConfig] = Field(
        default=None,
        description="可选：先调登录接口取 token，再注入到后续请求",
    )

    @property
    def resolved_urls(self) -> List[str]:
        """解析为待拉取的文档 URL 列表（去重、去空）"""
        if self.schema_urls:
            return [u.strip() for u in self.schema_urls if u and u.strip()]
        if self.schema_url and self.schema_url.strip():
            return [self.schema_url.strip()]
        return []


class ExecutedCaseResult(BaseModel):
    case: GeneratedTestCase
    passed: bool
    status_code: int
    duration_ms: float
    error: Optional[str] = None
    response_snippet: str


class ApiFromDocResult(BaseModel):
    total_apis: int
    total_cases: int
    executed: bool
    cases: List[GeneratedTestCase]
    results: Optional[List[ExecutedCaseResult]] = None


@router.post(
    "/api-test",
    response_model=ApiTestResult,
    summary="执行单个 HTTP 接口测试（需登录，将扣除积分）",
    tags=["api-test"],
)
async def run_api_test(
    payload: ApiTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiTestResult:
    """
    最小可用接口测试：
    - 发起 HTTP 请求
    - 记录状态码、耗时
    - 对比期望状态码
    - 返回响应内容片段，便于排查
    """
    # 简单计费策略：每次调用扣 1 积分
    need = credits_for_api_test()
    if current_user.credits < need:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"积分不足，本次需 {need} 积分，当前 {current_user.credits}，请联系管理员充值",
        )

    method = payload.method.upper()

    try:
        async with httpx.AsyncClient(timeout=payload.timeout_seconds) as client:
            resp = await client.request(
                method=method,
                url=payload.url,
                headers=payload.headers or None,
                params=payload.query or None,
                json=payload.body,
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"请求失败：{exc}",
        ) from exc

    snippet = resp.text[:1000] if resp.text else ""
    headers = {k: v for k, v in resp.headers.items()}

    passed = resp.status_code == payload.expect_status

    current_user.credits -= need
    db.add(current_user)
    db.commit()

    return ApiTestResult(
        passed=passed,
        status_code=resp.status_code,
        expect_status=payload.expect_status,
        duration_ms=resp.elapsed.total_seconds() * 1000 if resp.elapsed else 0.0,
        response_headers=headers,
        response_snippet=snippet,
        error=None if passed else "状态码不符合预期",
    )


def _extract_openapi_from_page(text: str) -> Optional[Dict[str, Any]]:
    """
    从 Apifox 等分享页中提取 OpenAPI：页面常把 spec 放在 ```yaml 或 ```json 代码块里。
    """
    # 匹配 ```yaml ... ``` 或 ```json ... ```
    for lang in ("yaml", "yml", "json"):
        m = re.search(
            r"```\s*" + re.escape(lang) + r"\s*\n(.*?)```",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if not m:
            continue
        block = m.group(1).strip()
        if not block:
            continue
        try:
            if lang == "json":
                return json.loads(block)
            return yaml.safe_load(block)
        except (ValueError, json.JSONDecodeError, yaml.YAMLError):
            continue
    # 尝试整段中从 openapi 或 "openapi" 开始的 YAML/JSON 块
    for start in ("openapi:", '"openapi"', "'openapi'"):
        idx = text.find(start)
        if idx == -1:
            continue
        try:
            doc = yaml.safe_load(text[idx:])
            if isinstance(doc, dict) and ("paths" in doc or "openapi" in doc):
                return doc
        except yaml.YAMLError:
            pass
        try:
            # 可能是 JSON，找从 { 开始的完整对象
            brace = text.find("{", idx)
            if brace != -1:
                depth = 0
                end = brace
                for i, c in enumerate(text[brace:], start=brace):
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            end = i
                            break
                if depth == 0:
                    doc = json.loads(text[brace : end + 1])
                    if isinstance(doc, dict) and "paths" in doc:
                        return doc
        except (ValueError, json.JSONDecodeError):
            pass
    return None


def _parse_doc_response(resp: httpx.Response) -> Optional[Dict[str, Any]]:
    """解析响应为 OpenAPI 文档（支持 JSON 或 YAML，含 Apifox 分享链接）"""
    text = (resp.text or "").strip()
    try:
        return json.loads(text)
    except (ValueError, json.JSONDecodeError):
        pass
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        pass
    # Apifox 分享页：文档在 Markdown 代码块内
    doc = _extract_openapi_from_page(text)
    if doc is not None and isinstance(doc, dict) and doc.get("paths"):
        return doc
    return None


def _get_nested(data: Dict[str, Any], path: str) -> Any:
    """按路径取值，如 data.token 或 $.data.accessToken；与 case_libraries 一致会去掉 $. 前缀"""
    if not path or not isinstance(data, dict):
        return None
    path = (path or "").strip()
    if path.startswith("$."):
        path = path[2:]
    if path == "$" or not path:
        return data
    keys = path.replace("[", ".").replace("]", "").split(".")
    for k in keys:
        if not k:
            continue
        if isinstance(data, dict) and k in data:
            data = data[k]
        else:
            return None
    return data


def _substitute_auth_placeholders(val: Any, username: Optional[str], password: Optional[str]) -> Any:
    """将 body 中的 {{username}}/{{password}} 替换为实际值"""
    if isinstance(val, str):
        s = val.replace("{{username}}", username or "")
        return s.replace("{{password}}", password or "")
    if isinstance(val, dict):
        return {k: _substitute_auth_placeholders(v, username, password) for k, v in val.items()}
    if isinstance(val, list):
        return [_substitute_auth_placeholders(x, username, password) for x in val]
    return val


async def _fetch_token(client: httpx.AsyncClient, auth: AuthConfig) -> Optional[str]:
    token, _, _ = await _fetch_token_with_info(client, auth)
    return token


async def _fetch_token_with_info(
    client: httpx.AsyncClient, auth: AuthConfig
) -> Tuple[Optional[str], int, str]:
    """调用登录接口，返回 (token, status_code, response_preview)"""
    if auth.body is not None:
        body = _substitute_auth_placeholders(auth.body, auth.username, auth.password)
        body = dict(body) if isinstance(body, dict) else {}
        if auth.username is not None:
            body.setdefault("username", auth.username)
        if auth.password is not None:
            body.setdefault("password", auth.password)
        resp = await client.request(
            auth.method.upper(),
            auth.login_url,
            json=body,
        )
    else:
        body = None
        if auth.username is not None or auth.password is not None:
            body = {"username": auth.username, "password": auth.password}
        resp = await client.request(
            auth.method.upper(),
            auth.login_url,
            json=body,
        )
    preview = (resp.text or "")[:500]
    if resp.status_code >= 400:
        return None, resp.status_code, preview
    try:
        data = resp.json()
    except (ValueError, json.JSONDecodeError):
        return None, resp.status_code, preview
    path = (auth.token_response_path or "").strip() or "access_token"
    token = _get_nested(data, path)
    if token is None and isinstance(data, dict):
        for fallback in ("data.accessToken", "data.access_token", "access_token", "accessToken"):
            if fallback != path:
                token = _get_nested(data, fallback)
                if token is not None:
                    break
    return (str(token) if token is not None else None, resp.status_code, preview)


def _detect_base_url_from_openapi(doc: Dict[str, Any]) -> Optional[str]:
    # OpenAPI 3.x: servers[0].url
    servers = doc.get("servers") or []
    if servers and isinstance(servers, list):
        url = servers[0].get("url")
        if isinstance(url, str):
            return url.rstrip("/")

    # Swagger 2.0: scheme + host + basePath
    if "swagger" in doc:
        scheme = "https"
        schemes = doc.get("schemes") or []
        if isinstance(schemes, list) and schemes:
            scheme = schemes[0]
        host = doc.get("host")
        base_path = doc.get("basePath", "") or ""
        if host:
            return f"{scheme}://{host}{base_path}".rstrip("/")

    return None


def _example_from_schema(schema: Optional[Dict[str, Any]]) -> Any:
    """根据 JSON Schema 生成示例值（用于 query/body 占位）。"""
    if not schema or not isinstance(schema, dict):
        return None
    if "example" in schema:
        return schema["example"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if "default" in schema:
        return schema["default"]
    type_ = schema.get("type")
    if type_ == "string":
        return schema.get("example") or ""
    if type_ == "integer" or type_ == "number":
        return schema.get("example", 0)
    if type_ == "boolean":
        return schema.get("example", False)
    if type_ == "array":
        items = schema.get("items")
        return [ _example_from_schema(items) ] if items else []
    if type_ == "object":
        props = schema.get("properties") or {}
        return { k: _example_from_schema(v) for k, v in props.items() }
    return None


def _resolve_ref(doc: Dict[str, Any], ref: str) -> Optional[Dict[str, Any]]:
    """解析 $ref 如 #/components/schemas/Foo。"""
    if not ref or not ref.startswith("#/"):
        return None
    parts = ref.split("/")[1:]
    cur: Any = doc
    for p in parts:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur if isinstance(cur, dict) else None


def _get_schema_from_media(media: Dict[str, Any], doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从 content['application/json'] 取 schema，支持 $ref。"""
    schema = media.get("schema")
    if not schema:
        return None
    if isinstance(schema, dict) and "$ref" in schema:
        return _resolve_ref(doc, schema["$ref"])
    return schema if isinstance(schema, dict) else None


def _build_object_from_schema(schema: Dict[str, Any], doc: Dict[str, Any]) -> Dict[str, Any]:
    """根据 object schema 的 properties/required 构建示例对象。"""
    if schema.get("$ref"):
        ref_schema = _resolve_ref(doc, schema["$ref"])
        if ref_schema:
            return _build_object_from_schema(ref_schema, doc)
        return {}
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    out: Dict[str, Any] = {}
    for k, v in props.items():
        if not isinstance(v, dict):
            continue
        if v.get("$ref"):
            ref_schema = _resolve_ref(doc, v["$ref"])
            if ref_schema:
                out[k] = _example_from_schema(ref_schema) if ref_schema.get("type") != "object" else _build_object_from_schema(ref_schema, doc)
            else:
                out[k] = _example_from_schema(v)
        else:
            out[k] = _example_from_schema(v)
    return out


def _extract_apis_from_doc(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    从 OpenAPI/Swagger 文档中提取接口列表，保留完整 operation 以便生成参数用例。
    """
    paths = doc.get("paths") or {}
    apis: List[Dict[str, Any]] = []

    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, meta in methods.items():
            method_upper = method.upper()
            if method_upper not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
                continue
            if not isinstance(meta, dict):
                continue
            summary = meta.get("summary") or meta.get("operationId") or ""
            apis.append({
                "path": path,
                "method": method_upper,
                "summary": summary,
                "operation": meta,
            })
    return apis


def _substitute_path_params(path: str, path_params: Dict[str, Any]) -> str:
    """将 path 中的 {param} 替换为 path_params 的值。"""
    out = path
    for k, v in path_params.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def _build_request_examples_from_operation(
    operation: Dict[str, Any],
    path: str,
    doc: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], str]:
    """
    从 operation 提取 path_params、query 示例、body 示例，以及替换后的 path。
    返回 (path_params_dict, query_dict, body_dict, path_after_substitute)。
    """
    path_params: Dict[str, Any] = {}
    query_params: Dict[str, Any] = {}
    body_dict: Dict[str, Any] = {}

    parameters = operation.get("parameters") or []
    for p in parameters:
        if not isinstance(p, dict):
            continue
        name = p.get("name")
        if not name:
            continue
        param_in = (p.get("in") or "query").lower()
        schema = p.get("schema")
        if isinstance(schema, dict) and "$ref" in schema:
            schema = _resolve_ref(doc, schema["$ref"])
        example = p.get("example")
        if example is not None:
            val = example
        elif schema:
            val = _example_from_schema(schema)
        else:
            val = "0"  # path 占位，避免 URL 残留 {id}
        if param_in == "path":
            path_params[name] = val
        elif param_in == "query":
            query_params[name] = val

    path_final = _substitute_path_params(path, path_params)

    request_body = operation.get("requestBody")
    if isinstance(request_body, dict):
        content = request_body.get("content") or {}
        media = content.get("application/json") or content.get("application/x-www-form-urlencoded")
        if media:
            if "example" in media:
                body_dict = dict(media["example"]) if isinstance(media["example"], dict) else {}
            elif "examples" in media and media["examples"]:
                first_ex = list(media["examples"].values())[0]
                if isinstance(first_ex, dict) and "value" in first_ex and isinstance(first_ex["value"], dict):
                    body_dict = first_ex["value"]
                else:
                    body_dict = {}
            else:
                schema = _get_schema_from_media(media, doc)
                if schema and (schema.get("type") == "object" or schema.get("properties")):
                    body_dict = _build_object_from_schema(schema, doc)
                elif schema:
                    body_dict = _example_from_schema(schema) or {}

    return path_params, query_params, body_dict, path_final


def _build_generated_cases(
    apis: List[Dict[str, Any]],
    base_url: Optional[str],
    max_cases_per_api: int,
    doc: Optional[Dict[str, Any]] = None,
) -> List[GeneratedTestCase]:
    """根据接口列表及 OpenAPI doc（用于 $ref）生成用例，含 query/body 参数设计。"""
    doc = doc or {}
    cases: List[GeneratedTestCase] = []
    for api in apis:
        path = api["path"]
        method = api["method"]
        summary = api.get("summary") or f"{method} {path}"
        operation = api.get("operation") or {}

        path_params, query_params, body_dict, path_final = _build_request_examples_from_operation(
            operation, path, doc
        )

        full_base = (base_url or "").rstrip("/") if base_url else ""
        if full_base:
            full_url = urljoin(full_base + "/", path_final.lstrip("/"))
        else:
            full_url = path_final

        case = GeneratedTestCase(
            name=summary,
            method=method,
            path=path_final,
            full_url=full_url,
            description=summary,
            expect_status=200,
            query=query_params if query_params else None,
            body=body_dict if body_dict else None,
        )
        cases.append(case)

    return cases


def parse_openapi_content_to_cases(
    content: str,
    base_url_override: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """从 OpenAPI 文件内容（JSON 或 YAML 字符串）解析并生成用例列表（不扣积分）。"""
    text = (content or "").strip()
    doc = None
    try:
        doc = json.loads(text)
    except (ValueError, json.JSONDecodeError):
        pass
    if doc is None:
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError:
            pass
    if not doc or not isinstance(doc, dict):
        raise ValueError("文件内容不是有效的 JSON 或 YAML 格式")
    paths = doc.get("paths") or {}
    if not paths:
        raise ValueError("文档中未包含任何接口定义（paths 为空）")
    apis = _extract_apis_from_doc(doc)
    if not apis:
        raise ValueError("未从文档中解析出任何接口")
    auto_base = _detect_base_url_from_openapi(doc)
    base = base_url_override or auto_base
    cases = _build_generated_cases(apis, base, max_cases_per_api=1, doc=doc)
    return [c.model_dump() for c in cases]


def _is_html_response(resp: httpx.Response) -> bool:
    ct = (resp.headers.get("content-type") or "").lower()
    if "text/html" in ct:
        return True
    text = (resp.text or "").strip()
    return text.startswith("<!") or text.startswith("<html")

def _openapi_fetch_error_message(one_url: str, is_apifox: bool) -> str:
    if is_apifox:
        return (
            "该链接是 Apifox 分享页（返回的是网页而非 OpenAPI 文档），无法直接解析。"
            "请在浏览器打开该链接，点击页面上的「导出」按钮，选择 OpenAPI(Swagger) 格式下载；"
            "或将文档改为可直接返回 JSON/YAML 的地址（如部分文档服务提供的 raw 链接）。"
        )
    return (
        f"该链接未返回有效的 OpenAPI/Swagger 文档（JSON 或 YAML）：{one_url}。"
        "若为 Apifox 分享链接，请先在分享页导出 OpenAPI 后再使用。"
    )


async def fetch_urls_and_build_case_dicts(
    urls: List[str],
    base_url: Optional[str],
) -> List[Dict[str, Any]]:
    """拉取多个文档地址，合并 paths，生成用例列表（字典形式，便于入库）。"""
    merged_paths: Dict[str, Any] = {}
    first_servers: List[Any] = []
    got_html_no_spec = False
    last_html_url: Optional[str] = None
    is_apifox_url = False
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for one_url in urls:
            resp = await client.get(one_url)
            resp.raise_for_status()
            doc = _parse_doc_response(resp)
            if not doc:
                if _is_html_response(resp):
                    got_html_no_spec = True
                    last_html_url = one_url
                    is_apifox_url = "apifox" in one_url.lower()
                continue
            paths = doc.get("paths") or {}
            for path, methods in paths.items():
                if not isinstance(methods, dict):
                    continue
                if path not in merged_paths:
                    merged_paths[path] = {}
                merged_paths[path].update(methods)
            if not first_servers and doc.get("servers"):
                first_servers = doc["servers"]
    merged_doc = {"paths": merged_paths, "servers": first_servers}
    apis = _extract_apis_from_doc(merged_doc)
    if not apis and got_html_no_spec and last_html_url:
        raise ValueError(_openapi_fetch_error_message(last_html_url, is_apifox_url))
    auto_base = _detect_base_url_from_openapi(merged_doc)
    base = base_url or auto_base
    cases = _build_generated_cases(apis, base, max_cases_per_api=1, doc=merged_doc)
    return [c.model_dump() for c in cases]


@router.post(
    "/api-test/from-doc",
    response_model=ApiFromDocResult,
    summary="从 Swagger/OpenAPI 文档生成测试用例（可选执行）",
    tags=["api-test"],
)
async def generate_tests_from_doc(
    payload: ApiFromDocRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiFromDocResult:
    urls = payload.resolved_urls
    if not urls:
        raise HTTPException(
            status_code=400,
            detail="请填写至少一个文档地址（schema_url 或 schema_urls）",
        )

    # 拉取并合并多个文档（支持 JSON 或 YAML，含 Apifox 分享链接）
    merged_paths: Dict[str, Any] = {}
    first_servers: List[Any] = []
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for one_url in urls:
            try:
                resp = await client.get(one_url)
                resp.raise_for_status()
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"拉取接口文档失败（{one_url}）：{exc}",
                ) from exc
            doc = _parse_doc_response(resp)
            if doc is None:
                msg = (
                    _openapi_fetch_error_message(one_url, "apifox" in one_url.lower())
                    if _is_html_response(resp)
                    else f"该链接不是有效的 JSON/YAML 文档：{one_url}"
                )
                raise HTTPException(status_code=400, detail=msg)
            paths = doc.get("paths") or {}
            for path, methods in paths.items():
                if not isinstance(methods, dict):
                    continue
                if path not in merged_paths:
                    merged_paths[path] = {}
                merged_paths[path].update(methods)
            if not first_servers and doc.get("servers"):
                first_servers = doc["servers"]

    merged_doc: Dict[str, Any] = {"paths": merged_paths, "servers": first_servers}

    # 提取 API 列表
    apis = _extract_apis_from_doc(merged_doc)
    if not apis:
        raise HTTPException(
            status_code=400,
            detail="在所有文档中未找到任何接口定义（paths 为空）",
        )

    # 确定基础地址
    auto_base = _detect_base_url_from_openapi(merged_doc)
    base_url = payload.base_url or auto_base

    cases = _build_generated_cases(apis, base_url, payload.max_cases_per_api, doc=merged_doc)

    executed = False
    exec_results: List[ExecutedCaseResult] = []

    # 若只生成不执行，直接返回
    if payload.only_generate:
        return ApiFromDocResult(
            total_apis=len(apis),
            total_cases=len(cases),
            executed=False,
            cases=cases,
            results=None,
        )

    credits_needed = credits_for_from_doc(only_generate=False, case_count=len(cases))
    if current_user.credits < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"积分不足，需要 {credits_needed}，当前仅有 {current_user.credits}，请联系管理员充值",
        )

    merged_headers: Dict[str, str] = dict(payload.extra_headers or {})
    merged_query: Dict[str, Any] = dict(payload.extra_query or {})

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        if payload.auth:
            token = await _fetch_token(client, payload.auth)
            if token:
                merged_headers[payload.auth.header_name] = payload.auth.header_prefix + token
            # 未取到 token 也继续执行，仅不带该 Header

        for case in cases:
            params = dict(merged_query)
            if case.query:
                params.update(case.query)
            json_body = case.body if case.method in ("POST", "PUT", "PATCH") else None
            try:
                resp_case = await client.request(
                    method=case.method,
                    url=case.full_url,
                    headers=merged_headers if merged_headers else None,
                    params=params if params else None,
                    json=json_body,
                )
                passed = resp_case.status_code == case.expect_status
                snippet = resp_case.text[:1000] if resp_case.text else ""
                exec_results.append(
                    ExecutedCaseResult(
                        case=case,
                        passed=passed,
                        status_code=resp_case.status_code,
                        duration_ms=resp_case.elapsed.total_seconds() * 1000
                        if resp_case.elapsed
                        else 0.0,
                        error=None if passed else "状态码不符合预期",
                        response_snippet=snippet,
                    )
                )
            except httpx.RequestError as exc:
                exec_results.append(
                    ExecutedCaseResult(
                        case=case,
                        passed=False,
                        status_code=0,
                        duration_ms=0.0,
                        error=f"请求失败：{exc}",
                        response_snippet="",
                    )
                )

    # 扣除积分
    current_user.credits -= credits_needed
    db.add(current_user)
    db.commit()

    executed = True

    return ApiFromDocResult(
        total_apis=len(apis),
        total_cases=len(cases),
        executed=executed,
        cases=cases,
        results=exec_results,
    )


