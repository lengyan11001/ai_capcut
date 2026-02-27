"""账号列表：登录型或静态 Token，执行用例时选用"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Account, User
from .auth import get_current_user

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    account_type: str = Field(..., pattern="^(login|static)$")
    login_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    token_response_path: Optional[str] = "access_token"
    token_header_name: Optional[str] = None   # 如 access-token、Authorization，默认 Authorization
    token_header_prefix: Optional[str] = None # 如 "" 或 "Bearer "，默认 "Bearer "
    login_body: Optional[dict] = None        # 自定义登录 Body，不填则用 {"username","password"}
    static_headers: Optional[dict] = None


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    account_type: Optional[str] = Field(None, pattern="^(login|static)$")
    login_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    token_response_path: Optional[str] = None
    token_header_name: Optional[str] = None
    token_header_prefix: Optional[str] = None
    login_body: Optional[dict] = None
    static_headers: Optional[dict] = None


def _account_to_out(a: Account) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "account_type": a.account_type,
        "login_url": a.login_url,
        "username": a.username,
        "password": a.password,
        "token_response_path": a.token_response_path,
        "token_header_name": getattr(a, "token_header_name", None),
        "token_header_prefix": getattr(a, "token_header_prefix", None),
        "login_body": getattr(a, "login_body", None),
        "static_headers": a.static_headers,
        "created_at": a.created_at.isoformat() if a.created_at else "",
    }


@router.get("", response_model=list)
def list_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.query(Account).filter(Account.user_id == current_user.id).order_by(Account.created_at.desc()).all()
    out = []
    for r in rows:
        d = _account_to_out(r)
        if d.get("password"):
            d["password"] = "********"
        out.append(d)
    return out


@router.post("", response_model=dict)
def create_account(
    payload: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = Account(
        user_id=current_user.id,
        name=payload.name,
        account_type=payload.account_type,
        login_url=payload.login_url,
        username=payload.username,
        password=payload.password,
        token_response_path=payload.token_response_path,
        token_header_name=payload.token_header_name,
        token_header_prefix=payload.token_header_prefix,
        login_body=payload.login_body,
        static_headers=payload.static_headers,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    d = _account_to_out(a)
    if d.get("password"):
        d["password"] = "********"
    return d


@router.get("/{account_id}", response_model=dict)
def get_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not a:
        raise HTTPException(status_code=404, detail="账号不存在")
    d = _account_to_out(a)
    if d.get("password"):
        d["password"] = "********"
    return d


@router.patch("/{account_id}", response_model=dict)
def update_account(
    account_id: int,
    payload: AccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not a:
        raise HTTPException(status_code=404, detail="账号不存在")
    if payload.name is not None:
        a.name = payload.name
    if payload.account_type is not None:
        a.account_type = payload.account_type
    if payload.login_url is not None:
        a.login_url = payload.login_url
    if payload.username is not None:
        a.username = payload.username
    if payload.password is not None:
        a.password = payload.password
    if payload.token_response_path is not None:
        a.token_response_path = payload.token_response_path
    if payload.token_header_name is not None:
        a.token_header_name = payload.token_header_name
    if payload.token_header_prefix is not None:
        a.token_header_prefix = payload.token_header_prefix
    if payload.login_body is not None:
        a.login_body = payload.login_body
    if payload.static_headers is not None:
        a.static_headers = payload.static_headers
    db.add(a)
    db.commit()
    db.refresh(a)
    d = _account_to_out(a)
    if d.get("password"):
        d["password"] = "********"
    return d


@router.delete("/{account_id}", status_code=204)
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = db.query(Account).filter(Account.id == account_id, Account.user_id == current_user.id).first()
    if not a:
        raise HTTPException(status_code=404, detail="账号不存在")
    db.delete(a)
    db.commit()
    return None
