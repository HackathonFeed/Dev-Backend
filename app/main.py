from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logger import setup_logging
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.rate_limit_middleware import RateLimitMiddleware
from app.services.avatar_service import ensure_avatar_dir, uses_supabase_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    if settings.use_supabase_data_layer:
        from app.integrations.supabase_client import get_supabase_client

        client = get_supabase_client()
        if client is None:
            logger.warning("Supabase REST is not configured")
        else:
            try:
                response = client.table("hackathons").select("id", count="exact").limit(1).execute()
                logger.info(f"Supabase REST connected ({response.count or 0} hackathons)")
            except Exception as exc:
                logger.error(f"Supabase REST connection failed: {exc}")

    yield
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)

    app.include_router(api_router, prefix=settings.api_prefix)

    if not uses_supabase_storage():
        uploads_dir = ensure_avatar_dir()
        app.mount("/uploads", StaticFiles(directory=str(uploads_dir.parent)), name="uploads")

    @app.get("/health")
    async def health_check():
        return {"success": True, "message": "Service is healthy", "data": {"status": "ok"}}

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": str(exc.detail)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "Validation error",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled error on {request.method} {request.url.path}: {exc}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Internal server error"},
        )

    return app


app = create_app()
