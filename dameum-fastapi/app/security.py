from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(
    name="X-API-Key",
    description="로컬 FastAPI와 프론트엔드가 공유하는 32자 이상의 API 키",
    auto_error=False,
)


async def require_api_key(
    request: Request, supplied_key: str | None = Security(api_key_header)
) -> None:
    expected_key = request.app.state.settings.api_key
    if supplied_key is None or not secrets.compare_digest(supplied_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_api_key", "message": "유효한 API 키가 필요합니다"},
            headers={"WWW-Authenticate": "ApiKey"},
        )


async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
    response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
    return response
