from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "AI 测试平台"
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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def cors_origins_list(self) -> List[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

