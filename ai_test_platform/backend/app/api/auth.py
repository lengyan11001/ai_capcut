import hashlib
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db import get_db
from ..models import User


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
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # 显式构造返回，避免 ORM 序列化问题
    return UserOut(id=user.id, email=user.email, credits=user.credits)


@router.post("/login", response_model=Token, summary="登录并获取访问令牌")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    access_token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=access_token)


@router.get("/me", response_model=UserOut, summary="当前用户信息与剩余积分")
def get_me(current_user: User = Depends(get_current_user)):
    return UserOut(id=current_user.id, email=current_user.email, credits=current_user.credits)


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
    }

