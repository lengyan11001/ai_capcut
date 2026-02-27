"""文档模版：保存文档地址，支持一键生成用例库"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CaseLibrary, DocumentTemplate, User
from .auth import get_current_user
from .api_test import fetch_urls_and_build_case_dicts

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
    }


@router.get("", response_model=List[dict])
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.query(DocumentTemplate).filter(DocumentTemplate.user_id == current_user.id).order_by(DocumentTemplate.created_at.desc()).all()
    return [_template_to_out(r) for r in rows]


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
    library_name: str = Field(..., min_length=1, max_length=255, description="新建用例库名称")


@router.post("/{template_id}/generate-cases", response_model=dict)
async def generate_cases_from_template(
    template_id: int,
    payload: GenerateCasesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """根据模版拉取文档并生成用例库（不扣积分，仅生成）"""
    t = db.query(DocumentTemplate).filter(DocumentTemplate.id == template_id, DocumentTemplate.user_id == current_user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="模版不存在")
    urls = [u.strip() for u in (t.schema_urls or []) if u and str(u).strip()]
    if not urls:
        raise HTTPException(status_code=400, detail="模版下没有有效的文档地址")
    try:
        cases = await fetch_urls_and_build_case_dicts(urls, t.base_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"拉取文档失败：{e}")
    if not cases:
        raise HTTPException(status_code=400, detail="未从文档中解析出任何接口")
    lib = CaseLibrary(
        user_id=current_user.id,
        name=payload.library_name,
        template_id=t.id,
        cases=cases,
    )
    db.add(lib)
    db.commit()
    db.refresh(lib)
    return {"id": lib.id, "name": lib.name, "cases_count": len(cases), "created_at": lib.created_at.isoformat()}
