from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "智能工作生活平台"
    environment: str = "dev"
    debug: bool = True
    secret_key: str = "CHANGE_ME_TO_A_RANDOM_SECRET_IN_PRODUCTION"
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    database_url: str = "sqlite:///./ai_test_platform.db"
    # 邮件发送配置（用于邮箱验证等）
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = True
    # 大模型配置（用于用例生成等）
    openai_api_key: str | None = None
    openai_base_url: str | None = None  # 可选，自定义网关或代理
    openai_provider: str | None = None  # 可选，当前配置的厂商，仅展示该厂商模型。可选值：deepseek / aliyun / volcengine
    # OpenClaw Gateway：配置后 /chat 将代理到 OpenClaw 的 Chat Completions，实现会话 + MCP 调用
    openclaw_gateway_url: str | None = None  # 学习实例 URL（如 http://127.0.0.1:18789），白名单用户使用
    openclaw_gateway_token: str | None = None  # 学习实例鉴权 token
    # 用户实例（多 agent、每用户独立 workspace）；未配置时所有用户共用上面单一 Gateway
    openclaw_gateway_url_users: str | None = None  # 如 http://127.0.0.1:18790
    openclaw_gateway_token_users: str | None = None  # 用户实例鉴权 token
    # 学习实例白名单：逗号分隔的 user id 或 email，仅这些账号走学习实例；空则按是否配置 url_users 决定（见 chat 路由）
    openclaw_learn_allowlist: str = ""  # 例如 "1" 或 "admin@example.com" 或 "1,2,admin@example.com"
    # 新用户注册赠送积分（控制成本）
    default_credits_for_new_user: int = 30
    # 充值接口密钥：请求头 X-Recharge-Token 与此一致时才允许充值
    recharge_secret: str | None = None
    # 管理接口密钥：请求头 X-Admin-Token 与此一致时才允许访问 /auth/model-pricing 等
    admin_secret: str | None = None
    # 智能对话用量限制（防过度使用，前期内部用可放宽；0 表示不限制）
    chat_daily_cap_per_user: int = 100  # 每用户每日最多 N 轮对话
    chat_rate_limit_per_minute: int = 30  # 每用户每分钟最多 N 次请求
    # MCP 能力代理相关（供独立 MCP HTTP 服务使用；后端保留字段以避免 .env 额外字段导致启动失败）
    capability_sutui_mcp_url: str | None = None
    capability_allowlist: str | None = None
    capability_catalog_path: str | None = None
    capability_upstream_urls_json: str | None = None
    # 养号计划 LLM（直接调用 OpenAI 兼容端点，不经 OpenClaw；优先级高于 OpenClaw）
    nurture_llm_base_url: str | None = None  # 如 https://api.ephone.chat/v1
    nurture_llm_api_key: str | None = None
    nurture_llm_model: str = "deepseek-chat"  # 发给端点的 model 名
    # 群控控制面配置
    control_agent_secret: str | None = None  # 本地 Agent 注册/拉任务鉴权密钥
    control_task_lease_seconds: int = 120
    control_agent_offline_seconds: int = 90

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def cors_origins_list(self) -> List[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

