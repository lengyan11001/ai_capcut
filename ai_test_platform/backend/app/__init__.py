import traceback
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.health import router as health_router
from .api.chat import router as chat_router
from .api.api_test import router as api_test_router
from .api.auth import router as auth_router
from .api.templates import router as templates_router
from .api.case_libraries import router as case_libraries_router
from .api.accounts import router as accounts_router
from .api.capabilities import router as capabilities_router
from .core.config import settings
from .db import Base, engine
from . import models  # noqa: F401


def _ensure_accounts_columns():
    """为已有数据库补充 accounts 表的新列（如 login_body）"""
    from sqlalchemy import text
    try:
        with engine.begin() as conn:
            if "sqlite" in (engine.url.drivername or ""):
                rp = conn.execute(text("PRAGMA table_info(accounts)"))
                rows = rp.fetchall()
                columns = [row[1] for row in rows] if rows else []
                if "login_body" not in columns:
                    conn.execute(text("ALTER TABLE accounts ADD COLUMN login_body JSON"))
    except Exception:
        pass


def _ensure_user_email_columns():
    """为已有数据库补充 users 表的 is_email_verified 列（旧库兼容）。"""
    from sqlalchemy import text

    try:
        with engine.begin() as conn:
            if "sqlite" in (engine.url.drivername or ""):
                rp = conn.execute(text("PRAGMA table_info(users)"))
                rows = rp.fetchall()
                columns = [row[1] for row in rows] if rows else []
                if "is_email_verified" not in columns:
                    # 使用 INTEGER 存储布尔值，默认 0（未验证）
                    conn.execute(
                        text(
                            "ALTER TABLE users ADD COLUMN is_email_verified INTEGER NOT NULL DEFAULT 0"
                        )
                    )
    except Exception:
        # 兼容旧库失败时不影响服务启动
        pass


def _ensure_document_template_columns():
    """为已有数据库补充 document_templates 表的新列（如 file_content）。"""
    from sqlalchemy import text

    try:
        with engine.begin() as conn:
            if "sqlite" in (engine.url.drivername or ""):
                rp = conn.execute(text("PRAGMA table_info(document_templates)"))
                rows = rp.fetchall()
                columns = [row[1] for row in rows] if rows else []
                if "file_content" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE document_templates ADD COLUMN file_content TEXT"
                        )
                    )
    except Exception:
        # 兼容旧库失败时不影响服务启动
        pass


def _ensure_case_generate_record_credits_reserved():
    """为已有数据库补充 case_generate_records.credits_reserved 列。"""
    from sqlalchemy import text

    try:
        with engine.begin() as conn:
            if "sqlite" in (engine.url.drivername or ""):
                rp = conn.execute(text("PRAGMA table_info(case_generate_records)"))
                rows = rp.fetchall()
                columns = [row[1] for row in rows] if rows else []
                if "credits_reserved" not in columns:
                    conn.execute(
                        text(
                            "ALTER TABLE case_generate_records ADD COLUMN credits_reserved INTEGER"
                        )
                    )
    except Exception:
        pass


def _seed_model_pricing():
    """首次部署或表为空时，将代码中的 LLM_MODELS 与 openclaw:default 写入 model_pricing。"""
    from .core.llm_client import LLM_MODELS
    from .db import SessionLocal
    from .models import ModelPricing

    db = SessionLocal()
    try:
        count = db.query(ModelPricing).count()
        if count > 0:
            return
        for model_id, cfg in LLM_MODELS.items():
            db.add(ModelPricing(
                model_id=model_id,
                display_name=cfg.display_name,
                provider=cfg.provider,
                input_price_per_m=cfg.input_price_per_m,
                output_price_per_m=cfg.output_price_per_m,
                currency=cfg.currency,
                margin_factor=cfg.margin_factor,
                enabled=True,
            ))
        db.add(ModelPricing(
            model_id="openclaw:default",
            display_name="OpenClaw 智能对话（默认）",
            provider="openclaw",
            input_price_per_m=0.28,
            output_price_per_m=0.42,
            currency="USD",
            margin_factor=1.5,
            enabled=True,
        ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _seed_capability_catalog():
    """首次部署或 capability_configs 为空时，从 mcp/capability_catalog.json 导入能力目录。"""
    import json
    from .db import SessionLocal
    from .models import CapabilityConfig

    catalog_path = Path(__file__).resolve().parent.parent.parent / "mcp" / "capability_catalog.json"
    if not catalog_path.exists():
        return
    db = SessionLocal()
    try:
        if db.query(CapabilityConfig).count() > 0:
            return
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return
        for capability_id, cfg in raw.items():
            if not isinstance(capability_id, str) or not isinstance(cfg, dict):
                continue
            db.add(
                CapabilityConfig(
                    capability_id=capability_id.strip(),
                    description=str(cfg.get("description") or capability_id),
                    upstream=str(cfg.get("upstream") or "sutui"),
                    upstream_tool=str(cfg.get("upstream_tool") or "").strip(),
                    arg_schema=cfg.get("arg_schema") if isinstance(cfg.get("arg_schema"), dict) else None,
                    enabled=bool(cfg.get("enabled", True)),
                    is_default=bool(cfg.get("is_default", capability_id in {"image.generate", "task.get_result"})),
                    unit_credits=int(cfg.get("unit_credits") or 0),
                )
            )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _ensure_capability_call_log_columns():
    """为已有数据库补充 capability_call_logs 表的新列。"""
    from sqlalchemy import text

    try:
        with engine.begin() as conn:
            if "sqlite" in (engine.url.drivername or ""):
                rp = conn.execute(text("PRAGMA table_info(capability_call_logs)"))
                rows = rp.fetchall()
                columns = [row[1] for row in rows] if rows else []
                if "response_payload" not in columns:
                    conn.execute(text("ALTER TABLE capability_call_logs ADD COLUMN response_payload JSON"))
                if "source" not in columns:
                    conn.execute(text("ALTER TABLE capability_call_logs ADD COLUMN source VARCHAR(64)"))
                if "chat_session_id" not in columns:
                    conn.execute(text("ALTER TABLE capability_call_logs ADD COLUMN chat_session_id VARCHAR(128)"))
                if "chat_context_id" not in columns:
                    conn.execute(text("ALTER TABLE capability_call_logs ADD COLUMN chat_context_id VARCHAR(128)"))
    except Exception:
        pass


def _ensure_capability_config_columns():
    """为已有数据库补充 capability_configs 表的新列。"""
    from sqlalchemy import text

    try:
        with engine.begin() as conn:
            if "sqlite" in (engine.url.drivername or ""):
                rp = conn.execute(text("PRAGMA table_info(capability_configs)"))
                rows = rp.fetchall()
                columns = [row[1] for row in rows] if rows else []
                if "is_default" not in columns:
                    conn.execute(
                        text("ALTER TABLE capability_configs ADD COLUMN is_default INTEGER NOT NULL DEFAULT 0")
                    )
    except Exception:
        pass


def _backfill_default_capabilities():
    """为既有能力目录补齐默认能力标记。"""
    from .db import SessionLocal
    from .models import CapabilityConfig

    db = SessionLocal()
    try:
        targets = {"image.generate", "task.get_result"}
        rows = db.query(CapabilityConfig).filter(CapabilityConfig.capability_id.in_(targets)).all()
        changed = False
        for row in rows:
            if not row.is_default:
                row.is_default = True
                changed = True
        if changed:
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def create_app() -> FastAPI:
    Base.metadata.create_all(bind=engine)
    _ensure_accounts_columns()
    _ensure_user_email_columns()
    _ensure_document_template_columns()
    _ensure_case_generate_record_credits_reserved()
    _ensure_capability_call_log_columns()
    _ensure_capability_config_columns()
    _seed_model_pricing()
    _seed_capability_catalog()
    _backfill_default_capabilities()

    app = FastAPI(
        title="智能工作生活平台 API",
        version="0.1.0",
        description="智能工作生活平台后端",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def catch_all(request: Request, exc: Exception):
        if settings.debug:
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal Server Error",
                    "debug": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    app.include_router(health_router, prefix="")
    app.include_router(auth_router, prefix="/auth")
    app.include_router(templates_router, prefix="")
    app.include_router(case_libraries_router, prefix="")
    app.include_router(accounts_router, prefix="")
    app.include_router(capabilities_router, prefix="")
    app.include_router(chat_router, prefix="")
    app.include_router(api_test_router, prefix="")

    static_dir = Path(__file__).resolve().parent.parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()

