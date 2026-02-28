from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class DocumentTemplate(Base):
    """文档模版：保存接口文档地址等，用于生成用例"""
    __tablename__ = "document_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_urls: Mapped[list] = mapped_column(JSON, nullable=False)  # ["url1", "url2"]
    base_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    extra_headers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    extra_query: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # 可选：直接存储上传的 OpenAPI 文件内容（JSON 或 YAML 文本）
    file_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CaseLibrary(Base):
    """用例库：某次生成的用例集合，用例可编辑"""
    __tablename__ = "case_libraries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("document_templates.id"), nullable=True)
    cases: Mapped[list] = mapped_column(JSON, nullable=False)  # [{"name","method","path","full_url","expect_status",...}]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class CaseGenerateRecord(Base):
    """用例生成记录：每次点击「创建用例」并（可选）调大模型时创建，成功或失败都记录原因"""
    __tablename__ = "case_generate_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("document_templates.id"), nullable=False, index=True)
    template_name: Mapped[str] = mapped_column(String(255), nullable=False)
    library_name: Mapped[str] = mapped_column(String(255), nullable=False)
    llm_model_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # running | success | failed
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 成功说明或失败原因
    library_id: Mapped[Optional[int]] = mapped_column(ForeignKey("case_libraries.id"), nullable=True)
    credits_reserved: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 预扣积分（任务结束时按实际消耗退款）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class CreditFlow(Base):
    """积分资金流水：扣费、退款、充值等记录"""
    __tablename__ = "credit_flows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    flow_type: Mapped[str] = mapped_column(String(32), nullable=False)  # deduct | refund | recharge
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # 正数：扣费为支出，退款/充值为收入
    balance_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 变动后余额
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    related_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # case_generate | execute | api_test | recharge
    related_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Account(Base):
    """账号：登录型或静态 Token，执行用例时选用"""
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False)  # "login" | "static"
    # login 型
    login_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    token_response_path: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    token_header_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)   # 登录后 token 写入的 Header 名，如 access-token 或 Authorization
    token_header_prefix: Mapped[Optional[str]] = mapped_column(String(32), nullable=True) # 值前缀，如空或 "Bearer "
    login_body: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 自定义登录请求体 JSON，不填则用 {"username","password"}；可含 {{username}}/{{password}} 占位
    # static 型
    static_headers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {"Authorization": "Bearer xxx"}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ModelPricing(Base):
    """模型价格配置：可调，优先于代码默认。按 input/output 元/百万 token + margin 换算积分。"""
    __tablename__ = "model_pricing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    model_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    input_price_per_m: Mapped[float] = mapped_column(Float, nullable=False)
    output_price_per_m: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)  # CNY / USD
    margin_factor: Mapped[float] = mapped_column(Float, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UsagePeriod(Base):
    """用量统计：用户 × 模型 × 周期，为会员 token 上限预留。"""
    __tablename__ = "usage_period"
    __table_args__ = (UniqueConstraint("user_id", "model_id", "period_start", name="uq_usage_period_user_model_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class EmailVerificationCode(Base):
    """邮箱验证码：用于注册/找回密码等场景"""

    __tablename__ = "email_verification_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


