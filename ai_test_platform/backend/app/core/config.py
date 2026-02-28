from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "OpenClaw 控制台"
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
    openclaw_gateway_url: str | None = None  # 如 http://127.0.0.1:18789
    openclaw_gateway_token: str | None = None  # Gateway 鉴权 token
    # 新用户注册赠送积分（控制成本）
    default_credits_for_new_user: int = 30
    # 充值接口密钥：请求头 X-Recharge-Token 与此一致时才允许充值
    recharge_secret: str | None = None
    # 管理接口密钥：请求头 X-Admin-Token 与此一致时才允许访问 /auth/model-pricing 等
    admin_secret: str | None = None
    # 智能对话用量限制（防过度使用，前期内部用可放宽；0 表示不限制）
    chat_daily_cap_per_user: int = 100  # 每用户每日最多 N 轮对话
    chat_rate_limit_per_minute: int = 30  # 每用户每分钟最多 N 次请求

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def cors_origins_list(self) -> List[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

