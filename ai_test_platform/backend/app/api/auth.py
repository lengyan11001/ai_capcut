import hashlib
from datetime import datetime, timedelta
from typing import Optional
import random
import logging

import bcrypt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.credit_flow import add_credit_flow
from ..core.llm_client import public_llm_pricing
from ..core import openclaw_pool
from ..db import get_db
from ..models import CreditFlow, EmailVerificationCode, ModelPricing, OpenClawInstance, User, UserOpenClawBinding
from ..core.email_sender import email_sender


router = APIRouter()
logger = logging.getLogger(__name__)


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
    role: str
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


def _is_admin_user(user: User) -> bool:
    role = (getattr(user, "role", "") or "").strip().lower()
    return role == "admin"


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

    default_credits = getattr(settings, "default_credits_for_new_user", 30)
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        credits=default_credits,
        is_email_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # 注册后自动分配 OpenClaw 实例绑定（实例池为空时跳过，不影响注册）
    try:
        binding = openclaw_pool.assign_instance_if_needed(db, user.id)
        if binding is None:
            logger.warning("openclaw_pool_empty user_id=%s email=%s", user.id, user.email)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("openclaw_assign_failed user_id=%s", user.id)
    # 发送邮箱验证码（若已配置邮件服务）
    _create_and_send_verification_code(db, user)
    # 显式构造返回，避免 ORM 序列化问题
    return UserOut(
        id=user.id,
        email=user.email,
        credits=user.credits,
        role=getattr(user, "role", "user") or "user",
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
        role=getattr(current_user, "role", "user") or "user",
        is_email_verified=current_user.is_email_verified,
    )


class AdminRechargeIn(BaseModel):
    user_id: int
    amount: int = Field(..., gt=0)
    description: Optional[str] = None


@router.get("/admin/users", summary="管理员用户列表（Bearer）")
def admin_list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    rows = db.query(User).order_by(User.id.asc()).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "credits": u.credits,
            "role": getattr(u, "role", "user") or "user",
            "is_email_verified": bool(getattr(u, "is_email_verified", False)),
            "created_at": u.created_at.isoformat() if u.created_at else "",
        }
        for u in rows
    ]


@router.post("/admin/recharge", summary="管理员充值积分（Bearer）")
def admin_recharge(
    payload: AdminRechargeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin_user(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    desc = (payload.description or "").strip() or f"管理员充值（admin={current_user.email}）"
    add_credit_flow(db, user, "recharge", payload.amount, desc, "recharge", None)
    db.commit()
    db.refresh(user)
    return {"detail": "充值成功", "credits": user.credits}


@router.get("/credit-flows", summary="积分资金流水（扣费、退款、充值）")
def list_credit_flows(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """当前用户的积分流水，按时间倒序。"""
    rows = (
        db.query(CreditFlow)
        .filter(CreditFlow.user_id == current_user.id)
        .order_by(CreditFlow.created_at.desc())
        .offset(offset)
        .limit(min(limit, 100))
        .all()
    )
    return [
        {
            "id": r.id,
            "flow_type": r.flow_type,
            "amount": r.amount,
            "balance_after": r.balance_after,
            "description": r.description,
            "related_type": r.related_type,
            "related_id": r.related_id,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


class RechargeIn(BaseModel):
    """充值请求：user_id 或 email 二选一，amount 为正整数。"""
    user_id: Optional[int] = None
    email: Optional[EmailStr] = None
    amount: int = Field(..., gt=0, description="充值积分数量")


@router.post("/recharge", summary="充值积分（需 X-Recharge-Token 与配置一致）")
def recharge(
    payload: RechargeIn,
    db: Session = Depends(get_db),
    x_recharge_token: Optional[str] = Header(None, alias="X-Recharge-Token"),
):
    """管理端或支付回调为指定用户增加积分。请求头 X-Recharge-Token 需与 .env 中 RECHARGE_SECRET 一致。"""
    if not getattr(settings, "recharge_secret", None) or settings.recharge_secret.strip() == "":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="未配置充值密钥")
    if x_recharge_token != settings.recharge_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="充值密钥错误")
    if payload.user_id is not None:
        user = db.query(User).filter(User.id == payload.user_id).first()
    elif payload.email:
        user = get_user_by_email(db, payload.email)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请提供 user_id 或 email")
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    add_credit_flow(db, user, "recharge", payload.amount, "充值", "recharge", None)
    db.commit()
    db.refresh(user)
    return {"detail": "充值成功", "credits": user.credits}


def _require_admin_token(x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    """管理接口：请求头 X-Admin-Token 需与配置一致。"""
    if not getattr(settings, "admin_secret", None) or (settings.admin_secret or "").strip() == "":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="未配置管理密钥")
    if x_admin_token != settings.admin_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="管理密钥错误")


class ModelPricingUpdate(BaseModel):
    """更新模型价格（均为可选，只更新提供的字段）。"""
    display_name: Optional[str] = None
    provider: Optional[str] = None
    input_price_per_m: Optional[float] = None
    output_price_per_m: Optional[float] = None
    currency: Optional[str] = None
    margin_factor: Optional[float] = None
    enabled: Optional[bool] = None


class OpenClawInstanceIn(BaseModel):
    """OpenClaw 实例池新增/更新请求。"""
    name: str
    base_url: str
    gateway_token: str
    default_agent_id: str = "main"
    max_users: Optional[int] = None
    enabled: bool = True


class OpenClawInstanceUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    gateway_token: Optional[str] = None
    default_agent_id: Optional[str] = None
    max_users: Optional[int] = None
    enabled: Optional[bool] = None


@router.get("/openclaw-instances", summary="OpenClaw 实例池列表（管理端，需 X-Admin-Token）")
def list_openclaw_instances(
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin_token),
):
    rows = db.query(OpenClawInstance).order_by(OpenClawInstance.id.asc()).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "base_url": r.base_url,
            "default_agent_id": r.default_agent_id,
            "max_users": r.max_users,
            "current_users": r.current_users,
            "enabled": r.enabled,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        }
        for r in rows
    ]


@router.post("/openclaw-instances", summary="新增 OpenClaw 实例（管理端，需 X-Admin-Token）")
def create_openclaw_instance(
    payload: OpenClawInstanceIn,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin_token),
):
    exists = db.query(OpenClawInstance).filter(OpenClawInstance.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="实例名称已存在")
    row = OpenClawInstance(
        name=payload.name.strip(),
        base_url=(payload.base_url or "").strip().rstrip("/"),
        gateway_token=(payload.gateway_token or "").strip(),
        default_agent_id=(payload.default_agent_id or "main").strip() or "main",
        max_users=payload.max_users,
        enabled=payload.enabled,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "name": row.name,
        "base_url": row.base_url,
        "default_agent_id": row.default_agent_id,
        "max_users": row.max_users,
        "current_users": row.current_users,
        "enabled": row.enabled,
    }


@router.put("/openclaw-instances/{instance_id}", summary="更新 OpenClaw 实例（管理端，需 X-Admin-Token）")
def update_openclaw_instance(
    instance_id: int,
    payload: OpenClawInstanceUpdate,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin_token),
):
    row = db.query(OpenClawInstance).filter(OpenClawInstance.id == instance_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="实例不存在")
    if payload.name is not None:
        row.name = payload.name.strip()
    if payload.base_url is not None:
        row.base_url = payload.base_url.strip().rstrip("/")
    if payload.gateway_token is not None:
        row.gateway_token = payload.gateway_token.strip()
    if payload.default_agent_id is not None:
        row.default_agent_id = payload.default_agent_id.strip() or "main"
    if payload.max_users is not None:
        row.max_users = payload.max_users
    if payload.enabled is not None:
        row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "name": row.name,
        "base_url": row.base_url,
        "default_agent_id": row.default_agent_id,
        "max_users": row.max_users,
        "current_users": row.current_users,
        "enabled": row.enabled,
    }


@router.get("/openclaw-bindings", summary="用户 OpenClaw 绑定列表（管理端，需 X-Admin-Token）")
def list_openclaw_bindings(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin_token),
):
    q = db.query(UserOpenClawBinding)
    if user_id is not None:
        q = q.filter(UserOpenClawBinding.user_id == user_id)
    rows = q.order_by(UserOpenClawBinding.created_at.desc()).all()
    out = []
    for r in rows:
        user = db.query(User).filter(User.id == r.user_id).first()
        ins = db.query(OpenClawInstance).filter(OpenClawInstance.id == r.instance_id).first()
        out.append(
            {
                "id": r.id,
                "user_id": r.user_id,
                "email": user.email if user else "",
                "instance_id": r.instance_id,
                "instance_name": ins.name if ins else "",
                "agent_id": r.agent_id,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "updated_at": r.updated_at.isoformat() if r.updated_at else "",
            }
        )
    return out


@router.post("/openclaw-bindings/assign/{user_id}", summary="为用户执行实例池分配（管理端，需 X-Admin-Token）")
def assign_openclaw_binding(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin_token),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    binding = openclaw_pool.assign_instance_if_needed(db, user_id)
    if binding is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="暂无可用 OpenClaw 实例，请先创建实例池")
    db.commit()
    db.refresh(binding)
    ins = db.query(OpenClawInstance).filter(OpenClawInstance.id == binding.instance_id).first()
    return {
        "user_id": binding.user_id,
        "email": user.email,
        "instance_id": binding.instance_id,
        "instance_name": ins.name if ins else "",
        "agent_id": binding.agent_id,
        "status": binding.status,
    }


@router.get("/model-pricing", summary="模型价格配置列表（管理端，需 X-Admin-Token）")
def list_model_pricing(
    model_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin_token),
):
    """查询 model_pricing 表。不传 model_id 时返回全部；传则按 model_id 过滤。"""
    q = db.query(ModelPricing)
    if model_id is not None and model_id.strip():
        q = q.filter(ModelPricing.model_id == model_id.strip())
    rows = q.order_by(ModelPricing.model_id).all()
    return [
        {
            "id": r.id,
            "model_id": r.model_id,
            "display_name": r.display_name,
            "provider": r.provider,
            "input_price_per_m": r.input_price_per_m,
            "output_price_per_m": r.output_price_per_m,
            "currency": r.currency,
            "margin_factor": r.margin_factor,
            "enabled": r.enabled,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
        }
        for r in rows
    ]


@router.put("/model-pricing/{model_id}", summary="更新模型价格（管理端，需 X-Admin-Token）")
def update_model_pricing(
    model_id: str,
    payload: ModelPricingUpdate,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin_token),
):
    """按 model_id 更新一条 model_pricing，仅更新请求体中提供的字段。"""
    row = db.query(ModelPricing).filter(ModelPricing.model_id == model_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该 model_id 不存在")
    if payload.display_name is not None:
        row.display_name = payload.display_name
    if payload.provider is not None:
        row.provider = payload.provider
    if payload.input_price_per_m is not None:
        row.input_price_per_m = payload.input_price_per_m
    if payload.output_price_per_m is not None:
        row.output_price_per_m = payload.output_price_per_m
    if payload.currency is not None:
        row.currency = payload.currency
    if payload.margin_factor is not None:
        row.margin_factor = payload.margin_factor
    if payload.enabled is not None:
        row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    return {
        "model_id": row.model_id,
        "display_name": row.display_name,
        "provider": row.provider,
        "input_price_per_m": row.input_price_per_m,
        "output_price_per_m": row.output_price_per_m,
        "currency": row.currency,
        "margin_factor": row.margin_factor,
        "enabled": row.enabled,
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


@router.get("/pricing", summary="计费规则（积分单价，公开）")
def get_pricing():
    from ..core.credits import CREDITS_PER_CALL
    return {
        "credits_per_call": CREDITS_PER_CALL,
        "tools": [
            {"name": "run_api_test", "credits": CREDITS_PER_CALL["api_test"], "desc": "单次接口测试"},
            {"name": "from_doc_execute", "credits_per_case": CREDITS_PER_CALL["from_doc_execute"], "desc": "从文档执行每条用例"},
            {"name": "from_doc_generate", "credits": CREDITS_PER_CALL["from_doc_generate"], "desc": "仅生成用例不执行"},
            {"name": "chat", "credits": CREDITS_PER_CALL.get("chat", 3), "desc": "智能对话每轮"},
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


