from __future__ import annotations

"""
简单的邮件发送工具，用于发送邮箱验证码等通知。

当前实现基于标准库 smtplib，通过环境变量配置 SMTP。
"""

import smtplib
from email.message import EmailMessage
from typing import Optional

from .config import settings


class EmailSender:
    def __init__(self) -> None:
        self.host: Optional[str] = settings.smtp_host
        self.port: int = settings.smtp_port
        self.user: Optional[str] = settings.smtp_user
        self.password: Optional[str] = settings.smtp_password
        self.from_addr: Optional[str] = settings.smtp_from
        self.use_tls: bool = settings.smtp_use_tls

    def is_configured(self) -> bool:
        return bool(self.host and self.port and self.from_addr)

    def send_verification_code(self, to_email: str, code: str) -> None:
        """
        发送邮箱验证码。

        若 SMTP 未配置，则静默返回（避免在开发环境因未配置邮件而报错）。
        """
        if not self.is_configured():
            # 开发环境可以仅打印日志，生产请确保配置完整
            return

        msg = EmailMessage()
        msg["Subject"] = f"{settings.app_name} 邮箱验证验证码"
        msg["From"] = self.from_addr
        msg["To"] = to_email

        text = (
            f"你好！\n\n"
            f"你正在注册/验证 {settings.app_name} 账号，验证码为：{code}\n"
            f"有效期 15 分钟，请勿泄露给他人。\n\n"
            f"如果这不是你本人的操作，请忽略本邮件。\n"
        )
        msg.set_content(text)

        with smtplib.SMTP(self.host, self.port, timeout=10) as server:
            if self.use_tls:
                server.starttls()
            if self.user and self.password:
                server.login(self.user, self.password)
            server.send_message(msg)


email_sender = EmailSender()

