from __future__ import annotations

from typing import Any

from app.schemas import ErrorResponse

TAG_HEALTH = "상태 확인"
TAG_RECORDING = "브라우저 녹음"
TAG_PROFILES = "목소리 프로필"
TAG_BOOKS = "동화책"
TAG_LULLABIES = "자장가"
TAG_SINGING_LULLABIES = "Seed-VC 가창 자장가"
TAG_LIBRARY = "콘텐츠 라이브러리"
TAG_JOBS = "비동기 작업"

OPENAPI_TAGS = [
    {
        "name": TAG_HEALTH,
        "description": "인증 없이 서버 생존 여부, 추론 backend와 대기 작업 수를 확인합니다.",
    },
    {
        "name": TAG_RECORDING,
        "description": (
            "프론트엔드가 getUserMedia·MediaRecorder로 마이크를 녹음하고 multipart Blob을 "
            "목소리 프로필 또는 동화 페이지 API에 업로드하기 위한 런타임 계약입니다."
        ),
    },
    {
        "name": TAG_PROFILES,
        "description": (
            "음성 소유자의 동의를 기록하고 5~20개의 발병 전·가족 기증·현재 음성 샘플로 "
            "VoxCPM2 참조 프로필을 구성합니다. 샘플 변경 후에는 미리듣기를 다시 생성해야 합니다."
        ),
    },
    {
        "name": TAG_BOOKS,
        "description": (
            "동화책 페이지 원문·이미지와 부모의 페이지별 녹음을 관리합니다. 녹음 요청은 "
            "STT → LLM 복원 → 감정 분류 → VoxCPM2 합성을 비동기로 실행합니다."
        ),
    },
    {
        "name": TAG_LULLABIES,
        "description": (
            "부모 음색으로 가사를 부드럽게 낭독한 WAV를 생성합니다. 반복과 타이머의 실제 "
            "재생 제어는 응답 설정을 사용해 프론트엔드에서 수행합니다."
        ),
    },
    {
        "name": TAG_SINGING_LULLABIES,
        "description": (
            "무반주 가창 프리셋을 선택하고 Seed-VC SVC 모델로 멜로디를 유지한 채 "
            "등록된 부모 음색으로 변환합니다. 기존 VoxCPM2 자장가 낭독 API와 분리됩니다."
        ),
    },
    {
        "name": TAG_LIBRARY,
        "description": "책과 자장가를 하나의 목록으로 조회하고 재생 진입 URL을 제공합니다.",
    },
    {
        "name": TAG_JOBS,
        "description": (
            "202 Accepted 응답으로 생성된 작업을 1~2초 간격으로 조회합니다. "
            "succeeded 또는 failed에서 폴링을 종료합니다."
        ),
    },
]


def error_response(description: str, code: str, message: str) -> dict[str, Any]:
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json": {"example": {"detail": {"code": code, "message": message}}}
        },
    }


COMMON_ERROR_RESPONSES = {
    401: error_response(
        "X-API-Key가 없거나 일치하지 않음",
        "invalid_api_key",
        "유효한 API 키가 필요합니다",
    ),
    422: {
        "model": ErrorResponse,
        "description": "경로·쿼리·본문·파일 필드 검증 실패",
        "content": {
            "application/json": {
                "example": {
                    "detail": {
                        "code": "validation_error",
                        "message": "요청 값이 올바르지 않습니다",
                        "errors": [{"field": "body.name", "message": "Field required"}],
                    }
                }
            }
        },
    },
    500: error_response(
        "처리되지 않은 서버 또는 모델 오류",
        "internal_error",
        "요청 처리 중 오류가 발생했습니다",
    ),
}
COMMON_ERROR_RESPONSES[401]["headers"] = {
    "WWW-Authenticate": {
        "description": "필요한 인증 방식",
        "schema": {"type": "string", "example": "ApiKey"},
    }
}

NOT_FOUND_RESPONSE = error_response(
    "요청한 리소스가 존재하지 않음",
    "not_found",
    "리소스를 찾을 수 없습니다",
)
PROFILE_NOT_READY_RESPONSE = error_response(
    "목소리 프로필의 미리듣기 확인이 완료되지 않음",
    "profile_not_ready",
    "미리듣기로 확인을 마친 목소리 프로필이 필요합니다",
)
SEEDVC_UNAVAILABLE_RESPONSE = error_response(
    "별도 Seed-VC CPU 런타임이 설치되지 않았거나 추론 큐가 가득 참",
    "seedvc_runtime_unavailable",
    "Seed-VC CPU 런타임을 먼저 설치해야 합니다",
)
SEEDVC_UNAVAILABLE_RESPONSE["content"]["application/json"] = {
    "examples": {
        "runtime_unavailable": {
            "summary": "Seed-VC 미설치",
            "value": {
                "detail": {
                    "code": "seedvc_runtime_unavailable",
                    "message": "Seed-VC CPU 런타임을 먼저 설치해야 합니다",
                }
            },
        },
        "queue_full": {
            "summary": "추론 큐 포화",
            "value": {
                "detail": {
                    "code": "queue_full",
                    "message": "추론 작업 대기열이 가득 찼습니다",
                }
            },
        },
    }
}
INSUFFICIENT_SAMPLES_RESPONSE = error_response(
    "음성 샘플이 5개 미만이거나 20개를 초과함",
    "insufficient_samples",
    "샘플 5~20개를 등록해야 합니다",
)
PROFILE_IN_USE_RESPONSE = error_response(
    "책 녹음이나 자장가가 프로필을 사용 중임",
    "profile_in_use",
    "이 프로필을 사용한 책 녹음과 자장가를 먼저 삭제해야 합니다",
)
SAMPLE_LIMIT_RESPONSE = error_response(
    "프로필의 샘플 개수가 20개에 도달함",
    "sample_limit",
    "샘플은 최대 20개까지 등록할 수 있습니다",
)
FILE_TOO_LARGE_RESPONSE = error_response(
    "파일이 서버의 업로드 허용 크기를 초과함",
    "file_too_large",
    "업로드 허용 크기를 초과했습니다",
)
UNSUPPORTED_AUDIO_RESPONSE = error_response(
    "파일 시그니처가 지원 오디오 형식이 아님",
    "unsupported_audio",
    "지원하지 않는 오디오 형식입니다",
)
QUEUE_FULL_RESPONSE = error_response(
    "로컬 추론 대기열이 가득 참. Retry-After 헤더 이후 재시도",
    "queue_full",
    "추론 작업 대기열이 가득 찼습니다",
)
QUEUE_FULL_RESPONSE["headers"] = {
    "Retry-After": {
        "description": "재시도 전 대기할 초",
        "schema": {"type": "integer", "example": 30},
    }
}

_AUDIO_CONTENT = {"audio/wav": {"schema": {"type": "string", "format": "binary"}}}
_AUDIO_HEADERS = {
    "Accept-Ranges": {
        "description": "바이트 범위 요청 지원 여부",
        "schema": {"type": "string", "example": "bytes"},
    },
    "Content-Range": {
        "description": "Range 요청 시 반환된 바이트 범위",
        "schema": {"type": "string", "example": "bytes 0-65535/384044"},
    },
    "ETag": {
        "description": "브라우저 캐시 검증 값",
        "schema": {"type": "string", "example": '"18f00ab-5dc2c"'},
    },
}

AUDIO_FILE_RESPONSE = {
    200: {
        "description": "전체 WAV 오디오",
        "content": _AUDIO_CONTENT,
        "headers": _AUDIO_HEADERS,
    },
    206: {
        "description": "Range 헤더에 해당하는 일부 WAV 오디오",
        "content": _AUDIO_CONTENT,
        "headers": _AUDIO_HEADERS,
    },
    416: {
        "description": "요청한 바이트 범위가 파일 크기를 벗어남",
        "content": {"text/plain": {"schema": {"type": "string"}}},
        "headers": {
            "Content-Range": {
                "description": "선택 가능한 전체 파일 크기",
                "schema": {"type": "string", "example": "*/384044"},
            }
        },
    },
    404: NOT_FOUND_RESPONSE,
}

IMAGE_FILE_RESPONSE = {
    200: {
        "description": "메타데이터가 제거된 WebP 페이지 이미지",
        "content": {"image/webp": {"schema": {"type": "string", "format": "binary"}}},
        "headers": {
            "ETag": {
                "description": "브라우저 캐시 검증 값",
                "schema": {"type": "string", "example": '"18f00ab-20f4"'},
            }
        },
    },
    404: NOT_FOUND_RESPONSE,
}
