from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api import router
from app.config import Settings, get_settings
from app.db import create_engine, create_schema, create_session_factory
from app.inference import InferencePipeline, configure_cpu_threads
from app.jobs import JobQueue
from app.security import add_security_headers
from app.storage import MediaStore

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.prepare_directories()
    configure_cpu_threads(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_engine(settings)
        await create_schema(engine)
        (settings.data_dir / "dameum.sqlite3").chmod(0o600)
        session_factory = create_session_factory(engine)
        media_store = MediaStore(
            settings.data_dir,
            settings.max_audio_bytes,
            settings.max_image_bytes,
            settings.max_audio_seconds,
        )
        pipeline = InferencePipeline(settings)
        job_queue = JobQueue(settings, session_factory, pipeline, media_store)
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.media_store = media_store
        app.state.job_queue = job_queue
        await job_queue.start()
        try:
            yield
        finally:
            await job_queue.stop()
            await engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="구음장애 부모의 발화를 고유 음색으로 명료하게 전달하는 로컬 REST API",
        lifespan=lifespan,
        docs_url="/docs" if settings.environment == "local" else None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "testserver"],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "Range", "If-None-Match"],
        expose_headers=["Content-Length", "Content-Range", "Accept-Ranges", "ETag"],
        max_age=600,
    )
    app.middleware("http")(add_security_headers)
    app.include_router(router)

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def ready(request: Request) -> dict[str, object]:
        return {
            "status": "ready",
            "inference_backend": settings.inference_backend,
            "queued_jobs": request.app.state.job_queue.queue.qsize(),
            "models": {
                "stt": settings.stt_model,
                "correction": settings.llm_model,
                "emotion": settings.emotion_model,
                "tts": settings.voxcpm_model,
            },
        }

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "validation_error",
                    "message": "요청 값이 올바르지 않습니다",
                    "errors": errors,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("처리되지 않은 API 오류", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "code": "internal_error",
                    "message": "요청 처리 중 오류가 발생했습니다",
                }
            },
        )

    return app
