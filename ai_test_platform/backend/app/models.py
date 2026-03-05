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
    role: Mapped[str] = mapped_column(String(32), default="user", nullable=False)  # admin|user
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


class OpenClawInstance(Base):
    """OpenClaw 实例池：注册时为用户自动分配实例。"""
    __tablename__ = "openclaw_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    gateway_token: Mapped[str] = mapped_column(String(255), nullable=False)
    default_agent_id: Mapped[str] = mapped_column(String(128), default="main", nullable=False)
    max_users: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # NULL 表示不设上限
    current_users: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UserOpenClawBinding(Base):
    """用户绑定的 OpenClaw 实例与 agent。"""
    __tablename__ = "user_openclaw_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True, index=True)
    instance_id: Mapped[int] = mapped_column(ForeignKey("openclaw_instances.id"), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(128), default="main", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="assigned", nullable=False)  # assigned | disabled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


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


class CapabilityConfig(Base):
    """平台能力目录：统一白标能力配置（可管理、可计费）。"""
    __tablename__ = "capability_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    capability_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    upstream: Mapped[str] = mapped_column(String(64), nullable=False, default="sutui")
    upstream_tool: Mapped[str] = mapped_column(String(128), nullable=False)
    arg_schema: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    unit_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class CapabilityPolicy(Base):
    """能力访问策略：按 user_id / email 做 allow/deny。"""
    __tablename__ = "capability_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    capability_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)  # user_id | email
    subject_value: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    effect: Mapped[str] = mapped_column(String(16), nullable=False, default="allow")  # allow | deny
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class CapabilityCallLog(Base):
    """能力调用审计：记录调用、结果、扣费与延迟。"""
    __tablename__ = "capability_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    capability_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    upstream: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    upstream_tool: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    credits_charged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    request_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # mcp_invoke | ui | other
    chat_session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    chat_context_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ChatTurnLog(Base):
    """智能会话归档：按上下文（能力入口）保存用户问答，便于在各 skill 入口回看。"""
    __tablename__ = "chat_turn_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    context_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)  # capability_id / domain
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_reply: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ControlAgent(Base):
    """群控执行节点（本地 Agent 实例）。"""
    __tablename__ = "control_agents"
    __table_args__ = (UniqueConstraint("agent_key", name="uq_control_agents_agent_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    host: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    labels: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="online", nullable=False)  # online|offline|disabled
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class MobileDevice(Base):
    """群控设备（手机）注册表。"""
    __tablename__ = "mobile_devices"
    __table_args__ = (UniqueConstraint("serial", name="uq_mobile_devices_serial"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    serial: Mapped[str] = mapped_column(String(128), nullable=False, index=True)  # 例：192.168.1.93:5555
    alias: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    platform: Mapped[str] = mapped_column(String(32), default="android", nullable=False)
    agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("control_agents.id"), nullable=True, index=True)
    adb_status: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)  # device|offline|unauthorized|unknown
    appium_status: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    account_attrs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # niche, phase, karma, tags 等，供任务按属性筛选设备
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ControlTask(Base):
    """群控任务。"""
    __tablename__ = "control_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), default="reddit", nullable=False)  # reddit|tiktok|...
    task_type: Mapped[str] = mapped_column(String(64), default="reddit_flow", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target_device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("mobile_devices.id"), nullable=True, index=True)
    target_account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("reddit_account_assets.id"), nullable=True, index=True)
    dispatch_group_id: Mapped[Optional[int]] = mapped_column(ForeignKey("control_dispatch_groups.id"), nullable=True, index=True)
    device_filter: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # niche, min_phase, min_karma, tags 等，按账号属性筛选设备
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )  # pending|running|success|failed|cancelled|timeout
    assigned_agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("control_agents.id"), nullable=True, index=True)
    assigned_device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("mobile_devices.id"), nullable=True, index=True)
    lease_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class TaskExecution(Base):
    """任务执行记录（一次任务可有多次执行尝试）。"""
    __tablename__ = "task_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("control_tasks.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("control_agents.id"), nullable=True, index=True)
    device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("mobile_devices.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)  # running|success|failed|cancelled
    step: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class RedditAccountAsset(Base):
    """Reddit 账号资产（系统录入或用户自有）。"""
    __tablename__ = "reddit_account_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="user", nullable=False)  # user|system
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)  # active|paused|disabled
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    account_attrs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ControlDispatchGroup(Base):
    """任务分组：保存一组设备与账号，供批量下发。"""
    __tablename__ = "control_dispatch_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    device_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    account_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UserDeviceAssignment(Base):
    """设备分配：普通用户只能看到被分配设备。"""
    __tablename__ = "user_device_assignments"
    __table_args__ = (UniqueConstraint("user_id", "device_id", name="uq_user_device_assignment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("mobile_devices.id"), nullable=False, index=True)
    assigned_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class UserRedditAccountAssignment(Base):
    """系统账号分配：普通用户可见分配给自己的系统账号。"""
    __tablename__ = "user_reddit_account_assignments"
    __table_args__ = (UniqueConstraint("user_id", "reddit_account_id", name="uq_user_reddit_account_assignment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    reddit_account_id: Mapped[int] = mapped_column(ForeignKey("reddit_account_assets.id"), nullable=False, index=True)
    assigned_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class TaskExecutionLog(Base):
    """执行过程日志（步骤、截图地址、结构化上下文）。"""
    __tablename__ = "task_execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("task_executions.id"), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(16), default="info", nullable=False)  # debug|info|warn|error
    message: Mapped[str] = mapped_column(Text, nullable=False)
    screenshot_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class RedditStrategyConfig(Base):
    """Reddit 养号/发帖策略（AI 生成或人工配置）。"""
    __tablename__ = "reddit_strategy_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general", nullable=False)  # fashion|3c|beauty|pet|general
    config: Mapped[dict] = mapped_column(JSON, nullable=False)  # nurture_phases, post_templates, target_subs 等
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RiskAnalysisReport(Base):
    """风控分析报告（AI 生成）。"""
    __tablename__ = "risk_analysis_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), default="reddit", nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    findings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

