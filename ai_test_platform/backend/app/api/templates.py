"""文档模版：保存文档地址，支持一键生成用例库"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_db
from ..models import CaseGenerateRecord, CaseLibrary, DocumentTemplate, User
from .auth import get_current_user
from .api_test import (
    fetch_urls_and_build_case_dicts,
    fetch_urls_and_get_merged_content,
    _count_apis_from_openapi_content,
    normalize_llm_cases,
    parse_openapi_content_to_cases,
)
from ..core.llm_client import call_llm, estimate_credits_for_apis, estimate_credits_for_openapi_doc

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    schema_urls: List[str] = Field(..., min_length=1)
    base_url: Optional[str] = None
    extra_headers: Optional[dict] = None
    extra_query: Optional[dict] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    schema_urls: Optional[List[str]] = None
    base_url: Optional[str] = None
    extra_headers: Optional[dict] = None
    extra_query: Optional[dict] = None


class TemplateOut(BaseModel):
    id: int
    name: str
    schema_urls: List[str]
    base_url: Optional[str]
    extra_headers: Optional[dict]
    extra_query: Optional[dict]
    created_at: str
    # 是否来源于上传文件（而非纯 URL）
    has_file: bool

    class Config:
        from_attributes = True


def _template_to_out(t: DocumentTemplate) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "schema_urls": t.schema_urls or [],
        "base_url": t.base_url,
        "extra_headers": t.extra_headers,
        "extra_query": t.extra_query,
        "created_at": t.created_at.isoformat() if t.created_at else "",
        "has_file": bool(getattr(t, "file_content", None)),
    }


@router.get("", response_model=List[dict])
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.query(DocumentTemplate).filter(DocumentTemplate.user_id == current_user.id).order_by(DocumentTemplate.created_at.desc()).all()
    return [_template_to_out(r) for r in rows]


@router.get("/generate-records", response_model=List[dict])
def list_generate_records(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用例生成记录：每次创建用例（含调大模型）都会有一条，成功/失败原因在 message 中"""
    rows = (
        db.query(CaseGenerateRecord)
        .filter(CaseGenerateRecord.user_id == current_user.id)
        .order_by(CaseGenerateRecord.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": r.id,
            "template_id": r.template_id,
            "template_name": r.template_name,
            "library_name": r.library_name,
            "llm_model_id": r.llm_model_id,
            "status": r.status,
            "message": r.message,
            "library_id": r.library_id,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in rows
    ]


@router.post("", response_model=dict)
def create_template(
    payload: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = DocumentTemplate(
        user_id=current_user.id,
        name=payload.name,
        schema_urls=payload.schema_urls,
        base_url=payload.base_url,
        extra_headers=payload.extra_headers,
        extra_query=payload.extra_query,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _template_to_out(t)


@router.post("/from-upload", response_model=dict)
async def create_template_from_upload(
    file: UploadFile = File(..., description="OpenAPI 文件，支持 JSON 或 YAML"),
    name: str = Form(..., min_length=1, max_length=255, description="模版名称"),
    base_url: Optional[str] = Form(None, description="可选，测试环境 base_url"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """通过上传 OpenAPI 文件创建文档模版（文件内容存储在数据库中）。"""
    if not file.filename or not file.filename.lower().endswith((".json", ".yaml", ".yml")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请上传 .json、.yaml 或 .yml 格式的 OpenAPI 文件",
        )
    try:
        content = (await file.read()).decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件编码异常，请使用 UTF-8 编码",
        )

    t = DocumentTemplate(
        user_id=current_user.id,
        name=name,
        schema_urls=[],  # 文件型模版不依赖远程 URL
        base_url=base_url,
        extra_headers=None,
        extra_query=None,
        file_content=content,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _template_to_out(t)


@router.get("/{template_id}", response_model=dict)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    t = db.query(DocumentTemplate).filter(DocumentTemplate.id == template_id, DocumentTemplate.user_id == current_user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="模版不存在")
    return _template_to_out(t)


@router.patch("/{template_id}", response_model=dict)
def update_template(
  template_id: int,
  payload: TemplateUpdate,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
    t = db.query(DocumentTemplate).filter(DocumentTemplate.id == template_id, DocumentTemplate.user_id == current_user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="模版不存在")
    if payload.name is not None:
        t.name = payload.name
    if payload.schema_urls is not None:
        t.schema_urls = payload.schema_urls
    if payload.base_url is not None:
        t.base_url = payload.base_url
    if payload.extra_headers is not None:
        t.extra_headers = payload.extra_headers
    if payload.extra_query is not None:
        t.extra_query = payload.extra_query
    db.add(t)
    db.commit()
    db.refresh(t)
    return _template_to_out(t)


@router.delete("/{template_id}", status_code=204)
def delete_template(
  template_id: int,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
    t = db.query(DocumentTemplate).filter(DocumentTemplate.id == template_id, DocumentTemplate.user_id == current_user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="模版不存在")
    db.delete(t)
    db.commit()
    return None


class GenerateCasesRequest(BaseModel):
    library_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="新建用例库名称；estimate_only 为 true 时可省略",
    )
    llm_model_id: Optional[str] = Field(
        default=None,
        description="可选：指定用于生成更详细用例说明的大模型 ID，不填则仅规则生成",
    )
    estimate_only: bool = Field(
        False,
        description="为 true 时仅根据文档接口数估算大模型积分，不调用模型、不创建用例库",
    )


@router.post("/{template_id}/generate-cases", response_model=dict)
async def generate_cases_from_template(
    template_id: int,
    payload: GenerateCasesRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """根据模版拉取文档并生成用例库。

    - 未指定大模型：仅按规则解析 OpenAPI 生成用例库（不扣积分）
    - 指定 llm_model_id：由大模型以测试专家身份设计完整用例（调用顺序、参数传递、用例数量由模型决定），按实际用量扣积分
    """
    t = db.query(DocumentTemplate).filter(DocumentTemplate.id == template_id, DocumentTemplate.user_id == current_user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="模版不存在")

    llm_model_id = payload.llm_model_id or None
    urls = [u.strip() for u in (t.schema_urls or []) if u and str(u).strip()]
    file_content = getattr(t, "file_content", None)
    base_url = t.base_url or ""

    # 使用大模型时：获取 OpenAPI 全文供模型分析；否则按规则解析得到 cases
    use_llm = bool(llm_model_id)
    openapi_content: Optional[str] = None
    cases: Optional[List[dict]] = None

    if use_llm:
        if urls:
            try:
                openapi_content, base_url = await fetch_urls_and_get_merged_content(urls, t.base_url)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"拉取文档失败：{e}")
        elif file_content:
            openapi_content = file_content
        else:
            raise HTTPException(status_code=400, detail="模版下没有有效的文档地址或文件内容")
        if not openapi_content or not openapi_content.strip():
            raise HTTPException(status_code=400, detail="未获取到有效文档内容")
        api_count = _count_apis_from_openapi_content(openapi_content)
        if api_count == 0:
            raise HTTPException(status_code=400, detail="文档中未解析出任何接口")
    else:
        if urls:
            try:
                cases = await fetch_urls_and_build_case_dicts(urls, t.base_url)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"拉取文档失败：{e}")
        else:
            if not file_content:
                raise HTTPException(status_code=400, detail="模版下没有有效的文档地址或文件内容")
            try:
                cases = parse_openapi_content_to_cases(file_content, base_url_override=t.base_url or None)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        if not cases:
            raise HTTPException(status_code=400, detail="未从文档中解析出任何接口")

    # 仅预估：不调用模型、不创建用例库
    if payload.estimate_only:
        llm_estimate: Optional[dict] = None
        total_apis = api_count if use_llm else len(cases)
        total_cases_approx = (max(int(api_count * 2.5), 10) if use_llm else len(cases))
        if use_llm:
            llm_estimate = estimate_credits_for_openapi_doc(
                llm_model_id, len(openapi_content or ""), api_count
            )
        return {
            "estimate_only": True,
            "total_apis": total_apis,
            "total_cases": total_cases_approx,
            "llm_model_id": llm_model_id,
            "llm_estimate": llm_estimate,
        }

    if not payload.library_name or not payload.library_name.strip():
        raise HTTPException(status_code=400, detail="请填写用例库名称")

    record = CaseGenerateRecord(
        user_id=current_user.id,
        template_id=t.id,
        template_name=t.name,
        library_name=payload.library_name.strip(),
        llm_model_id=llm_model_id,
        status="running",
        message="生成中…",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    try:
        if use_llm:
            est = estimate_credits_for_openapi_doc(
                llm_model_id, len(openapi_content or ""), api_count
            )
            est_credits = int((est or {}).get("estimated_credits") or 0)
            if est_credits > 0 and current_user.credits < est_credits:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=f"积分不足，本次预计需 {est_credits} 积分，当前 {current_user.credits}",
                )
            background_tasks.add_task(
                _run_generate_cases_job,
                record_id=record.id,
                cases=None,
                openapi_content=openapi_content,
                base_url=base_url,
            )
        else:
            background_tasks.add_task(
                _run_generate_cases_job,
                record_id=record.id,
                cases=cases,
                openapi_content=None,
                base_url=None,
            )

        return {
            "task_record_id": record.id,
            "status": record.status,
            "message": "已创建生成任务，可在下方用例生成记录中查看进度",
        }
    except Exception as e:
        detail = getattr(e, "detail", str(e))
        record.status = "failed"
        record.message = (detail if isinstance(detail, str) else str(detail))[:2000]
        record.finished_at = datetime.utcnow()
        db.add(record)
        db.commit()
        raise


def _run_generate_cases_job(
    record_id: int,
    cases: Optional[List[dict]] = None,
    openapi_content: Optional[str] = None,
    base_url: Optional[str] = None,
) -> None:
    """后台任务：若提供 openapi_content 则由大模型设计完整用例并入库，否则直接使用 cases 入库。"""
    db = SessionLocal()
    try:
        record = db.query(CaseGenerateRecord).filter(CaseGenerateRecord.id == record_id).first()
        if not record:
            return

        user = db.query(User).filter(User.id == record.user_id).first()
        template = db.query(DocumentTemplate).filter(DocumentTemplate.id == record.template_id).first()
        if not user or not template:
            record.status = "failed"
            record.message = "用户或模版不存在"
            record.finished_at = datetime.utcnow()
            db.add(record)
            db.commit()
            return

        llm_model_id = record.llm_model_id
        llm_credits_used: Optional[int] = None
        final_cases: List[dict] = []

        try:
            if openapi_content and base_url is not None and llm_model_id:
                # 方案二：大模型以测试专家身份设计完整用例（调用顺序、参数传递、用例数量由模型决定）
                system_prompt = (
                    "你是一名资深接口测试专家，擅长根据 OpenAPI 文档设计完整、可执行的接口测试用例。\n"
                    "请完成以下工作：\n"
                    "1. 必须覆盖文档中的每一个接口（每个 path+method 至少有一条用例），再在此基础上增加关键流程的多步骤用例与异常/边界用例。\n"
                    "2. 分析接口依赖与调用顺序（例如先登录再创建再查询），按执行顺序输出用例数组。\n"
                    "3. 明确参数传递：若某接口依赖前面接口的返回值（如 id、token），在响应中通过 extract 抽取变量，在后续用例的 path/query/body/headers 中用 {{变量名}} 引用。\n"
                    "输出格式：仅输出一个 JSON 对象，且包含键 \"cases\"，值为用例数组。每条用例需包含：name, method, path, description, expect_status；可选：full_url, query, body, headers, extract。\n"
                    "extract 格式为对象，键为变量名，值为从该接口响应中取值的 JSON 路径，如 \"$.data.access_token\"。path/query/body/headers 中可用 {{变量名}} 引用前面步骤 extract 的变量。\n"
                    "只输出该 JSON，不要 markdown 包裹或多余说明。"
                )
                # 截断过长文档，避免超出模型上下文
                content_for_llm = (openapi_content or "").strip()
                if len(content_for_llm) > 120000:
                    content_for_llm = content_for_llm[:120000] + "\n\n... (文档已截断)"
                user_prompt = (
                    "以下是一份 OpenAPI 文档（JSON），基础地址 base_url 为："
                    + (base_url or "")
                    + "\n\n请以测试专家身份设计完整测试用例集，输出格式为 {\"cases\": [ {...}, ... ]}。\n\n"
                    "文档内容：\n"
                    + content_for_llm
                )
                llm_result = call_llm(
                    model_id=llm_model_id,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.3,
                    max_tokens=8192,
                )
                raw = str(llm_result.get("content") or "").strip()
                llm_credits_used = int(llm_result.get("credits_used") or 0)

                # 尝试从 markdown 代码块中取出 JSON
                if "```" in raw:
                    for part in raw.split("```"):
                        part = part.strip()
                        if part.startswith("json"):
                            part = part[4:].strip()
                        if part.startswith("{"):
                            raw = part
                            break
                parsed: Optional[dict] = None
                try:
                    parsed = json.loads(raw)
                except (ValueError, json.JSONDecodeError):
                    pass
                if not parsed or not isinstance(parsed, dict):
                    raise RuntimeError("大模型返回的不是有效 JSON 对象，无法解析用例列表")
                raw_cases = parsed.get("cases")
                if not isinstance(raw_cases, list):
                    raise RuntimeError("大模型返回的 JSON 中缺少 cases 数组")
                final_cases = normalize_llm_cases(raw_cases, base_url or "")
                if not final_cases:
                    raise RuntimeError("大模型未生成任何有效用例")

                if llm_credits_used > 0:
                    if user.credits < llm_credits_used:
                        raise RuntimeError(
                            f"积分不足，本次大模型生成需 {llm_credits_used} 积分，当前 {user.credits}"
                        )
                    user.credits -= llm_credits_used
                    db.add(user)
                    db.commit()
            else:
                # 未使用大模型：直接使用规则解析的 cases
                if not cases:
                    record.status = "failed"
                    record.message = "未提供用例数据"
                    record.finished_at = datetime.utcnow()
                    db.add(record)
                    db.commit()
                    return
                final_cases = cases

            lib = CaseLibrary(
                user_id=user.id,
                name=record.library_name,
                template_id=template.id,
                cases=final_cases,
            )
            db.add(lib)
            db.commit()
            db.refresh(lib)

            record.status = "success"
            msg = f"已生成用例库「{lib.name}」，共 {len(final_cases)} 条用例"
            if llm_credits_used:
                msg += f"，消耗大模型积分 {llm_credits_used}"
            record.message = msg
            record.library_id = lib.id
            record.finished_at = datetime.utcnow()
            db.add(record)
            db.commit()
        except Exception as e:  # noqa: BLE001
            record.status = "failed"
            detail = str(e).strip() or repr(e)
            record.message = detail[:2000]
            record.finished_at = datetime.utcnow()
            db.add(record)
            db.commit()
    finally:
        db.close()
