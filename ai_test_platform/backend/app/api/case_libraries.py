"""用例库：编辑用例、选择账号执行（支持顺序与响应链）"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.credits import credits_for_from_doc
from ..db import get_db
from ..models import Account, CaseLibrary, User
from .auth import get_current_user
from .api_test import _fetch_token_with_info, AuthConfig, parse_openapi_content_to_cases

router = APIRouter(prefix="/case-libraries", tags=["case-libraries"])


class CaseItem(BaseModel):
    name: str
    method: str
    path: str
    full_url: str
    description: Optional[str] = None
    expect_status: int = 200


class LibraryUpdateCases(BaseModel):
    cases: List[dict] = Field(..., description="用例列表，每项含 name, method, path, full_url, expect_status 等")


class ExecuteRequest(BaseModel):
    account_id: int = Field(..., description="本次执行使用的账号 ID")
    case_index: Optional[int] = Field(None, description="仅执行该下标的一条用例；不传则执行全部")
    case_indices: Optional[List[int]] = Field(None, description="仅执行这些下标的用例（按顺序）；与 case_index 二选一，不传则执行全部")


def _get_merged_headers_for_account(account: Account) -> dict:
    """根据账号类型返回请求头（登录则需先请求 token，这里只返回 static 或占位；执行时再调登录）"""
    if account.account_type == "static" and account.static_headers:
        return dict(account.static_headers)
    return {}


def _get_by_json_path(data: Any, path: str) -> Any:
    """按 JSON 路径取值，如 $.data.task_id 或 data.task_id，支持 data.list[0].id。"""
    if not path or not isinstance(data, (dict, list)):
        return None
    path = path.strip()
    if path.startswith("$."):
        path = path[2:]
    if not path:
        return data
    parts = re.split(r"\.|\[|\]", path)
    parts = [p.strip() for p in parts if p.strip()]
    cur = data
    for p in parts:
        if cur is None:
            return None
        if isinstance(cur, list):
            try:
                cur = cur[int(p)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    return cur


def _substitute_placeholders(val: Any, context: Dict[str, Any]) -> Any:
    """将字符串中的 {{var_name}} 替换为 context 中的值；对 dict/list 递归。"""
    if isinstance(val, str):
        for k, v in context.items():
            if v is None:
                v = ""
            val = val.replace("{{" + k + "}}", str(v))
        return val
    if isinstance(val, dict):
        return {k: _substitute_placeholders(v, context) for k, v in val.items()}
    if isinstance(val, list):
        return [_substitute_placeholders(x, context) for x in val]
    return val


async def _get_headers_with_login(
    client: httpx.AsyncClient, account: Account
) -> Tuple[dict, Optional[dict]]:
    """返回 (请求头, 登录结果信息)。登录结果仅登录型账号时有值。"""
    if account.account_type == "static" and account.static_headers:
        return dict(account.static_headers), None
    if account.account_type == "login" and account.login_url:
        header_name = getattr(account, "token_header_name", None) or "Authorization"
        header_prefix = getattr(account, "token_header_prefix", None)
        if header_prefix is None or (isinstance(header_prefix, str) and not header_prefix.strip()):
            header_prefix = ""
        auth = AuthConfig(
            login_url=account.login_url,
            method="POST",
            username=account.username,
            password=account.password,
            body=getattr(account, "login_body", None),
            token_response_path=account.token_response_path or "access_token",
            header_name=header_name,
            header_prefix=header_prefix,
        )
        token, status_code, response_preview = await _fetch_token_with_info(client, auth)
        login_result = {
            "success": bool(token),
            "status_code": status_code,
            "response_preview": response_preview,
        }
        if token:
            return {header_name: header_prefix + token}, login_result
        return {}, login_result
    return {}, None


@router.post("/from-upload", response_model=dict)
async def create_library_from_upload(
    file: UploadFile = File(..., description="OpenAPI 文件，支持 JSON 或 YAML"),
    library_name: str = Form(..., min_length=1, max_length=255, description="用例库名称"),
    base_url: Optional[str] = Form(None, description="可选，测试环境 base_url"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传 OpenAPI 文件并生成用例库（不扣积分）。适用于 Apifox 导出文件等。"""
    if not file.filename or not file.filename.lower().endswith((".json", ".yaml", ".yml")):
        raise HTTPException(
            status_code=400,
            detail="请上传 .json、.yaml 或 .yml 格式的 OpenAPI 文件",
        )
    try:
        content = (await file.read()).decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码异常，请使用 UTF-8 编码")
    try:
        cases = parse_openapi_content_to_cases(content, base_url_override=base_url or None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    lib = CaseLibrary(
        user_id=current_user.id,
        name=library_name,
        template_id=None,
        cases=cases,
    )
    db.add(lib)
    db.commit()
    db.refresh(lib)
    return {
        "id": lib.id,
        "name": lib.name,
        "cases_count": len(cases),
        "created_at": lib.created_at.isoformat() if lib.created_at else "",
    }


@router.get("", response_model=List[dict])
def list_libraries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.query(CaseLibrary).filter(CaseLibrary.user_id == current_user.id).order_by(CaseLibrary.updated_at.desc()).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "template_id": r.template_id,
            "cases_count": len(r.cases or []),
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        }
        for r in rows
    ]


@router.get("/{library_id}", response_model=dict)
def get_library(
    library_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lib = db.query(CaseLibrary).filter(CaseLibrary.id == library_id, CaseLibrary.user_id == current_user.id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="用例库不存在")
    return {
        "id": lib.id,
        "name": lib.name,
        "template_id": lib.template_id,
        "cases": lib.cases or [],
        "created_at": lib.created_at.isoformat() if lib.created_at else "",
        "updated_at": lib.updated_at.isoformat() if lib.updated_at else "",
    }


@router.patch("/{library_id}", response_model=dict)
def update_library_cases(
    library_id: int,
    payload: LibraryUpdateCases,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lib = db.query(CaseLibrary).filter(CaseLibrary.id == library_id, CaseLibrary.user_id == current_user.id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="用例库不存在")
    lib.cases = payload.cases
    db.add(lib)
    db.commit()
    db.refresh(lib)
    return {"id": lib.id, "cases_count": len(lib.cases or [])}


@router.delete("/{library_id}", status_code=204)
def delete_library(
    library_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lib = db.query(CaseLibrary).filter(CaseLibrary.id == library_id, CaseLibrary.user_id == current_user.id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="用例库不存在")
    db.delete(lib)
    db.commit()
    return None


@router.post("/{library_id}/execute", response_model=dict)
async def execute_library(
    library_id: int,
    payload: ExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """使用指定账号执行用例库中全部用例，按条数扣积分"""
    lib = db.query(CaseLibrary).filter(CaseLibrary.id == library_id, CaseLibrary.user_id == current_user.id).first()
    if not lib:
        raise HTTPException(status_code=404, detail="用例库不存在")
    account = db.query(Account).filter(Account.id == payload.account_id, Account.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    all_cases = lib.cases or []
    if not all_cases:
        raise HTTPException(status_code=400, detail="用例库为空")
    if payload.case_indices is not None and len(payload.case_indices) > 0:
        cases = [all_cases[i] for i in payload.case_indices if 0 <= i < len(all_cases)]
    elif payload.case_index is not None:
        if payload.case_index < 0 or payload.case_index >= len(all_cases):
            raise HTTPException(status_code=400, detail="case_index 越界")
        cases = [all_cases[payload.case_index]]
    else:
        cases = all_cases
    credits_needed = credits_for_from_doc(only_generate=False, case_count=len(cases))
    if current_user.credits < credits_needed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"积分不足，需要 {credits_needed}，当前 {current_user.credits}",
        )
    results = []
    context: Dict[str, Any] = {}
    login_result: Optional[dict] = None
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        headers, login_result = await _get_headers_with_login(client, account)
        for c in cases:
            method = (c.get("method") or "GET").upper()
            url = _substitute_placeholders((c.get("full_url") or c.get("path") or ""), context)
            expect = c.get("expect_status", 200)
            if expect is not None:
                try:
                    expect = int(expect)
                except (TypeError, ValueError):
                    expect = 200
            else:
                expect = 200
            params = c.get("query")
            if isinstance(params, dict):
                params = _substitute_placeholders(dict(params), context)
            else:
                params = None
            json_body = c.get("body")
            if isinstance(json_body, dict):
                json_body = _substitute_placeholders(dict(json_body), context)
            elif isinstance(json_body, str) and json_body.strip():
                substituted = _substitute_placeholders(json_body, context)
                try:
                    json_body = json.loads(substituted)
                except (ValueError, json.JSONDecodeError):
                    json_body = None
            else:
                json_body = None
            case_headers = c.get("headers")
            if isinstance(case_headers, dict) and case_headers:
                case_headers = _substitute_placeholders(dict(case_headers), context)
                merged_headers = dict(headers or {})
                for k, v in case_headers.items():
                    if v is not None:
                        merged_headers[str(k)] = str(v)
            else:
                merged_headers = dict(headers or {}) if headers else {}
            try:
                resp = await client.request(
                    method=method,
                    url=url,
                    headers=merged_headers if merged_headers else None,
                    params=params,
                    json=json_body if method in ("POST", "PUT", "PATCH") else None,
                )
                passed = resp.status_code == expect
                snippet = (resp.text or "")[:2000]
                results.append({
                    "case": c,
                    "passed": passed,
                    "status_code": resp.status_code,
                    "duration_ms": resp.elapsed.total_seconds() * 1000 if resp.elapsed else 0,
                    "error": None if passed else "状态码不符合预期",
                    "response_snippet": snippet,
                    "request_url": url,
                    "request_params": params,
                    "request_body": json_body,
                    "request_headers": merged_headers,
                })
                extract = c.get("extract")
                if isinstance(extract, dict) and extract and passed:
                    try:
                        data = resp.json()
                        for var_name, json_path in extract.items():
                            if isinstance(json_path, str):
                                context[var_name] = _get_by_json_path(data, json_path)
                    except (ValueError, json.JSONDecodeError):
                        pass
            except httpx.RequestError as e:
                results.append({
                    "case": c,
                    "passed": False,
                    "status_code": 0,
                    "duration_ms": 0,
                    "error": str(e),
                    "response_snippet": "",
                    "request_url": url,
                    "request_params": params,
                    "request_body": json_body,
                    "request_headers": merged_headers,
                })
    current_user.credits -= credits_needed
    db.add(current_user)
    db.commit()
    passed_count = sum(1 for r in results if r["passed"])
    return {
        "total": len(results),
        "passed": passed_count,
        "failed": len(results) - passed_count,
        "credits_used": credits_needed,
        "credits_left": current_user.credits,
        "login_result": login_result,
        "results": results,
    }
