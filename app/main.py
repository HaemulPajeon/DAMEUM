from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.api import router
from app.config import Settings, get_settings
from app.db import create_engine, create_schema, create_session_factory
from app.inference import InferencePipeline, configure_cpu_threads
from app.jobs import JobQueue
from app.openapi import OPENAPI_TAGS, TAG_HEALTH
from app.schemas import HealthLive, HealthReady
from app.security import add_security_headers
from app.storage import MediaStore

logger = logging.getLogger(__name__)


def stable_operation_id(route: APIRoute) -> str:
    # 함수명을 고정 operationId로 사용해 프론트 API 클라이언트의 불필요한 변경을 막는다.
    return route.name


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
        description=(
            "구음장애 부모의 발화를 **STT → LLM 문장 복원 → 감정 분류 → VoxCPM2**로 "
            "처리해 부모 고유 음색으로 전달하는 로컬 REST API입니다.\n\n"
            "모든 `/v1` 요청은 `X-API-Key`가 필요합니다. 생성 요청은 `202 Accepted`와 "
            "`status_url`을 반환하며, 프론트엔드는 1~2초 간격으로 작업을 조회해야 합니다."
        ),
        lifespan=lifespan,
        docs_url="/docs" if settings.environment == "local" else None,
        redoc_url=None,
        swagger_ui_parameters={
            "deepLinking": True,
            "displayRequestDuration": True,
            "filter": True,
            "showExtensions": True,
            "defaultModelsExpandDepth": 2,
        },
        openapi_tags=OPENAPI_TAGS,
        servers=[
            {
                "url": "http://127.0.0.1:8000",
                "description": "로컬 FastAPI 서버",
            }
        ],
        generate_unique_id_function=stable_operation_id,
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

    @app.get(
        "/health/live",
        tags=[TAG_HEALTH],
        summary="API 프로세스 생존 확인",
        description="인증 없이 프로세스가 HTTP 요청을 처리할 수 있는지 확인합니다.",
        response_description="프로세스 생존 상태",
        response_model=HealthLive,
    )
    async def live() -> HealthLive:
        return {"status": "ok"}

    @app.get(
        "/health/ready",
        tags=[TAG_HEALTH],
        summary="추론 서버 준비 상태 확인",
        description=(
            "인증 없이 현재 추론 backend, 모델 식별자와 대기 작업 수를 확인합니다. "
            "모델 가중치의 사전 로딩을 의미하지는 않습니다."
        ),
        response_description="서버와 추론 큐 구성",
        response_model=HealthReady,
    )
    async def ready(request: Request) -> HealthReady:
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
