"""文档模版：保存文档地址，支持一键生成用例库"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CaseGenerateRecord, CaseLibrary, DocumentTemplate, User
from .auth import get_current_user
from .api_test import fetch_urls_and_build_case_dicts, parse_openapi_content_to_cases
from ..core.llm_client import call_llm, estimate_credits_for_apis

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """根据模版拉取文档并生成用例库。

    - 默认仅按规则解析 OpenAPI 文档生成用例库（不扣积分）
    - 若指定 llm_model_id，则会调用大模型生成更详细的用例说明，并按实际用量扣积分
    """
    t = db.query(DocumentTemplate).filter(DocumentTemplate.id == template_id, DocumentTemplate.user_id == current_user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="模版不存在")
    # 1. 从模版获取接口用例（规则生成）
    cases: List[dict]
    urls = [u.strip() for u in (t.schema_urls or []) if u and str(u).strip()]
    if urls:
        try:
            cases = await fetch_urls_and_build_case_dicts(urls, t.base_url)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"拉取文档失败：{e}")
    else:
        content = getattr(t, "file_content", None)
        if not content:
            raise HTTPException(status_code=400, detail="模版下没有有效的文档地址或文件内容")
        try:
            cases = parse_openapi_content_to_cases(content, base_url_override=t.base_url or None)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if not cases:
        raise HTTPException(status_code=400, detail="未从文档中解析出任何接口")

    llm_model_id = payload.llm_model_id or None

    # 仅预估：根据接口数估算大模型积分，不调用模型、不创建用例库
    if payload.estimate_only:
        llm_estimate: Optional[dict] = None
        if llm_model_id:
            llm_estimate = estimate_credits_for_apis(llm_model_id, api_count=len(cases))
        return {
            "estimate_only": True,
            "total_apis": len(cases),
            "total_cases": len(cases),
            "llm_model_id": llm_model_id,
            "llm_estimate": llm_estimate,
        }

    if not payload.library_name or not payload.library_name.strip():
        raise HTTPException(status_code=400, detail="请填写用例库名称")

    # 创建一条生成记录（成功或失败都会更新原因给用户看）
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

    llm_credits_used: Optional[int] = None
    try:
        # 2. 若指定了大模型，为每条用例生成更详细说明，并按用量扣积分
        if llm_model_id:
            # 先按接口数预估一次大模型积分，用于余额校验与提示
            est = estimate_credits_for_apis(llm_model_id, api_count=len(cases))
            est_credits = int((est or {}).get("estimated_credits") or 0)
            if est_credits > 0 and current_user.credits < est_credits:
                # 在实际调用前直接提示余额不足，避免跑到一半才失败
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=f"积分不足，本次预计需 {est_credits} 积分，当前 {current_user.credits}",
                )

            system_prompt = (
                "你是一名资深接口测试工程师，擅长根据 OpenAPI 文档设计高质量接口测试用例。"
                "现在给你一组基于文档自动解析的初始用例，请你为每条用例生成更详细的中文说明，"
                "包括覆盖的场景、关键参数、边界条件等。"
            )
            simple_cases = [
                {
                    "index": idx,
                    "name": c.get("name"),
                    "method": c.get("method"),
                    "path": c.get("path"),
                    "full_url": c.get("full_url"),
                    "expect_status": c.get("expect_status", 200),
                }
                for idx, c in enumerate(cases)
            ]
            user_prompt = (
                "下面是根据接口文档自动解析出的初始测试用例列表（JSON）：\n"
                f"{json.dumps(simple_cases, ensure_ascii=False, indent=2)}\n\n"
                "请你生成一个 JSON 数组，数组中的每一项对应一条用例，格式为：\n"
                '{ "index": number, "description": string }\n'
                "其中 index 对应上面列表中的 index 字段，description 为该用例的详细中文说明。\n"
                "只输出 JSON，不要输出多余文字。"
            )
            try:
                llm_result = await asyncio.to_thread(
                        call_llm,
                    llm_model_id,
                    system_prompt,
                    user_prompt,
                    0.2,
                )
                content = str(llm_result.get("content") or "").strip()
                llm_credits_used = int(llm_result.get("credits_used") or 0)
                # 解析返回 JSON，按 index 覆盖 description
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, list):
                        desc_map: Dict[int, str] = {}
                        for item in parsed:
                            if not isinstance(item, dict):
                                continue
                            idx = item.get("index")
                            desc = item.get("description")
                            if isinstance(idx, int) and isinstance(desc, str):
                                desc_map[idx] = desc.strip()
                        for i, c in enumerate(cases):
                            if i in desc_map and desc_map[i]:
                                c["description"] = desc_map[i]
                except (ValueError, json.JSONDecodeError):
                    # 解析失败则忽略，仅保留原始 cases
                    pass
            except Exception as e:  # noqa: BLE001
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"调用大模型生成用例说明失败：{e}",
                ) from e

            # 扣除大模型积分
            if llm_credits_used and llm_credits_used > 0:
                if current_user.credits < llm_credits_used:
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail=f"积分不足，本次大模型生成需 {llm_credits_used} 积分，当前 {current_user.credits}",
                    )
                current_user.credits -= llm_credits_used
                db.add(current_user)
                db.commit()

        # 3. 创建用例库
        lib = CaseLibrary(
            user_id=current_user.id,
            name=payload.library_name.strip(),
            template_id=t.id,
            cases=cases,
        )
        db.add(lib)
        db.commit()
        db.refresh(lib)

        # 更新记录：成功
        record.status = "success"
        record.message = f"已生成用例库「{lib.name}」，共 {len(cases)} 条用例"
        if llm_credits_used:
            record.message += f"，消耗大模型积分 {llm_credits_used}"
        record.library_id = lib.id
        record.finished_at = datetime.utcnow()
        db.add(record)
        db.commit()

        return {
            "id": lib.id,
            "name": lib.name,
            "cases_count": len(cases),
            "created_at": lib.created_at.isoformat() if lib.created_at else "",
            "llm_credits_used": llm_credits_used,
        }
    except Exception as e:
        # 更新记录：失败原因展示给用户
        record.status = "failed"
        detail = getattr(e, "detail", str(e))
        record.message = (detail if isinstance(detail, str) else str(detail))[:2000]
        record.finished_at = datetime.utcnow()
        db.add(record)
        db.commit()
        raise
