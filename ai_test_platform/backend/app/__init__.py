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


def create_app() -> FastAPI:
    Base.metadata.create_all(bind=engine)
    _ensure_accounts_columns()

    app = FastAPI(
        title="AI 测试平台 API",
        version="0.1.0",
        description="对话式测试平台后端（起步阶段）",
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

