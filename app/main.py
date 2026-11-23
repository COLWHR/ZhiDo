from __future__ import annotations

import logging
import mimetypes
import os
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.ratelimit import RateLimitMiddleware, SecurityHeadersMiddleware
from app.db.session import db_manager
from utils import LLMServiceError

# Some Windows/Python builds do not map WebP in the system MIME table, which makes
# StaticFiles and FileResponse send avatars as application/octet-stream.
mimetypes.add_type("image/webp", ".webp")


class _SecretRedactionFilter(logging.Filter):
    """Keep JWTs / api keys out of application logs."""

    _patterns = (
        re.compile(r"(token=)[^&\s\"']+", re.IGNORECASE),
        re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE),
        re.compile(r"(\"?(?:access_token|refresh_token|password|api_key)\"?\s*[:=]\s*\")[^\"]+", re.IGNORECASE),
    )

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        for pattern in self._patterns:
            message = pattern.sub(lambda m: m.group(1) + "***", message)
        record.msg = message
        record.args = ()
        return True


def _configure_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    root = logging.getLogger()
    root.addFilter(_SecretRedactionFilter())
    for handler in root.handlers:
        handler.addFilter(_SecretRedactionFilter())


_configure_logging()
logger = logging.getLogger(__name__)


try:
    db_manager.init_db()
except Exception as exc:
    logger.error("Database initialization failed: %s", exc, exc_info=True)


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback

    error_id = uuid.uuid4().hex[:12]
    logger.error("Global exception [%s]: %s\n%s", error_id, exc, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "detail": "Internal server error",
            "message": "服务器内部错误，请稍后重试",
            "error_id": error_id,
            "data": None,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "detail": exc.detail,
            "message": exc.detail,
            "data": None,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error: %s", exc.errors())
    return JSONResponse(
        status_code=400,
        content={
            "code": 400,
            "detail": exc.errors(),
            "message": "请求参数验证失败",
            "data": None,
        },
    )


@app.exception_handler(LLMServiceError)
async def llm_service_exception_handler(request: Request, exc: LLMServiceError):
    logger.error("LLM service error on %s (%s): %s", request.url.path, exc.kind, exc.details or exc.message)

    if request.url.path.startswith(f"{settings.API_V1_STR}/agents/chat"):
        return JSONResponse(
            status_code=200,
            content={
                "content": f"抱歉，时空之门当前无法调用大模型服务：{exc.message}",
                "thought": None,
            },
        )

    return JSONResponse(
        status_code=503,
        content={
            "code": 503,
            "detail": exc.message,
            "message": exc.message,
            "data": None,
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With", "Cache-Control"],
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.on_event("startup")
async def _reconcile_forum_state():
    """Forums left 'running' by a previous process can never finish on their own."""
    try:
        from app.services.forum_service import reconcile_running_forums
        from app.services.system_config_service import refresh_config_cache

        conn = db_manager.get_connection()
        refresh_config_cache(conn)
        closed = reconcile_running_forums(conn)
        if closed:
            logger.warning("Reconciled %s stale running forum(s) to closed on startup.", closed)
    except Exception as exc:
        logger.warning("Startup reconciliation skipped: %s", exc)

base_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(base_dir)

uploads_dir = os.path.join(root_dir, "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

frontend_dist = os.path.join(root_dir, "frontend", "dist")
if not os.path.exists(frontend_dist):
    frontend_dist = os.path.join(root_dir, "..", "frontend", "dist")

logger.info("Frontend dist path: %s, exists: %s", frontend_dist, os.path.exists(frontend_dist))

if os.path.exists(frontend_dist):
    legacy_assets_dir = os.path.join(frontend_dist, "assets")
    modern_assets_dir = os.path.join(frontend_dist, "static")

    if os.path.exists(legacy_assets_dir):
        app.mount("/assets", StaticFiles(directory=legacy_assets_dir), name="assets")

    if os.path.exists(modern_assets_dir):
        app.mount("/static", StaticFiles(directory=modern_assets_dir), name="static")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api"):
            return JSONResponse(status_code=404, content={"detail": "API endpoint not found"})

        dist_root = Path(frontend_dist).resolve()
        try:
            file_path = (dist_root / full_path).resolve()
        except (OSError, ValueError):
            file_path = dist_root / "__invalid__"

        # 只允许命中 dist 目录内的真实文件，防止 ../ 穿越读取项目源码或 .env
        if file_path.is_relative_to(dist_root) and file_path.is_file():
            return FileResponse(file_path)

        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)

        return JSONResponse(status_code=404, content={"detail": "Not Found"})


@app.get("/")
def root():
    index_path = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Welcome to MADF API. Frontend not found.", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
