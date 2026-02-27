import hashlib
from datetime import datetime, timedelta
from typing import Optional
import random

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.llm_client import public_llm_pricing
from ..db import get_db
from ..models import EmailVerificationCode, User
from ..core.email_sender import email_sender


router = APIRouter()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 小时


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    credits: int
    is_email_verified: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _password_to_bcrypt_input(password: str) -> bytes:
    """bcrypt 只支持最多 72 字节，超长时先做 SHA256 再交给 bcrypt。"""
    raw = password.encode("utf-8")
    if len(raw) <= 72:
        return raw
    return hashlib.sha256(raw).hexdigest().encode("ascii")


def get_password_hash(password: str) -> str:
    data = _password_to_bcrypt_input(password)
    return bcrypt.hashpw(data, bcrypt.gensalt()).decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    data = _password_to_bcrypt_input(plain_password)
    return bcrypt.checkpw(data, hashed_password.encode("ascii"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id: int = int(payload.get("sub"))
        if user_id is None:
            raise credentials_exception
    except (JWTError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


@router.post("/register", response_model=UserOut, summary="注册新用户")
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    existing = get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(status_code=400, detail="该邮箱已注册")

    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        credits=100,
        is_email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # 发送邮箱验证码（若已配置邮件服务）
    _create_and_send_verification_code(db, user)
    # 显式构造返回，避免 ORM 序列化问题
    return UserOut(
        id=user.id,
        email=user.email,
        credits=user.credits,
        is_email_verified=user.is_email_verified,
    )


@router.post("/login", response_model=Token, summary="登录并获取访问令牌")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    # 未完成邮箱验证的账号禁止登录
    if not getattr(user, "is_email_verified", False):
        raise HTTPException(
            status_code=400,
            detail="该邮箱尚未完成验证，请先输入验证码完成验证后再登录",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=access_token)


@router.get("/me", response_model=UserOut, summary="当前用户信息与剩余积分")
def get_me(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        email=current_user.email,
        credits=current_user.credits,
        is_email_verified=current_user.is_email_verified,
    )


@router.get("/pricing", summary="计费规则（积分单价，公开）")
def get_pricing():
    from ..core.credits import CREDITS_PER_CALL
    return {
        "credits_per_call": CREDITS_PER_CALL,
        "tools": [
            {"name": "run_api_test", "credits": CREDITS_PER_CALL["api_test"], "desc": "单次接口测试"},
            {"name": "from_doc_execute", "credits_per_case": CREDITS_PER_CALL["from_doc_execute"], "desc": "从文档执行每条用例"},
            {"name": "from_doc_generate", "credits": CREDITS_PER_CALL["from_doc_generate"], "desc": "仅生成用例不执行"},
        ],
        "llm": public_llm_pricing(),
    }


class VerifyEmailIn(BaseModel):
    email: EmailStr
    code: str


def _generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def _create_and_send_verification_code(db: Session, user: User) -> None:
    """为用户创建一条新的验证码记录并发送邮件（若配置了 SMTP）。"""
    code = _generate_code()
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=15)
    rec = EmailVerificationCode(
        user_id=user.id,
        email=user.email,
        code=code,
        expires_at=expires_at,
        used_at=None,
        created_at=now,
    )
    db.add(rec)
    db.commit()
    # 发送邮件（若未配置，将静默返回）
    try:
        email_sender.send_verification_code(user.email, code)
    except Exception:
        # 邮件失败不阻断注册流程，可在日志中观测
        pass


@router.post("/verify-email", response_model=Token, summary="验证邮箱验证码并登录")
def verify_email(payload: VerifyEmailIn, db: Session = Depends(get_db)):
    user = get_user_by_email(db, payload.email)
    if not user:
        raise HTTPException(status_code=400, detail="用户不存在")

    # 查找最新一条验证码
    rec = (
        db.query(EmailVerificationCode)
        .filter(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.email == payload.email,
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .first()
    )
    now = datetime.utcnow()
    if (
        not rec
        or rec.used_at is not None
        or rec.expires_at < now
        or rec.code != payload.code
    ):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    rec.used_at = now
    user.is_email_verified = True
    db.add_all([rec, user])
    db.commit()

    # 验证成功后直接登录，返回访问令牌
    access_token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=access_token)


class ResendVerifyEmailIn(BaseModel):
    email: EmailStr


@router.post("/resend-verification", summary="重新发送邮箱验证码")
def resend_verification(payload: ResendVerifyEmailIn, db: Session = Depends(get_db)):
    user = get_user_by_email(db, payload.email)
    if not user:
        raise HTTPException(status_code=400, detail="用户不存在")
    if user.is_email_verified:
        raise HTTPException(status_code=400, detail="该邮箱已完成验证")

    # 简单限流：距离上次发送不足 60 秒则拒绝
    last = (
        db.query(EmailVerificationCode)
        .filter(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.email == payload.email,
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .first()
    )
    now = datetime.utcnow()
    if last and (now - last.created_at).total_seconds() < 60:
        raise HTTPException(status_code=429, detail="发送过于频繁，请稍后再试")

    _create_and_send_verification_code(db, user)
    return {"detail": "验证码已重新发送，如未收到请检查垃圾邮箱或稍后重试"}


