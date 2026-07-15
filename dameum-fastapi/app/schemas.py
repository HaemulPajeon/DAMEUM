from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProfileStatusValue = Literal["draft", "ready", "generating", "failed"]
JobStatusValue = Literal["queued", "running", "succeeded", "failed"]
EmotionValue = Literal["기쁨", "슬픔", "분노", "불안", "당황", "상처", "중립"]


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ValidationIssue(ApiModel):
    field: str = Field(description="오류가 발생한 요청 필드 경로", examples=["body.name"])
    message: str = Field(description="필드 검증 실패 사유", examples=["Field required"])


class ErrorDetail(ApiModel):
    code: str = Field(
        description="프론트엔드 분기 처리용 안정적인 오류 코드", examples=["not_found"]
    )
    message: str = Field(
        description="사용자에게 표시할 수 있는 한글 오류 메시지",
        examples=["목소리 프로필을(를) 찾을 수 없습니다"],
    )
    errors: list[ValidationIssue] | None = Field(
        default=None,
        description="요청 검증 실패 시 필드별 상세 오류",
    )


class ErrorResponse(ApiModel):
    detail: ErrorDetail = Field(description="공통 API 오류 본문")


class HealthLive(ApiModel):
    status: Literal["ok"] = Field(default="ok", description="API 프로세스 생존 상태")


class ModelConfiguration(ApiModel):
    stt: str = Field(
        description="STT 기본 모델과 구음장애 LoRA 어댑터 식별자",
        examples=["openai/whisper-small+whisper-small-lora-dysarthria"],
    )
    correction: str = Field(description="문장 복원 LLM 식별자", examples=["Qwen3-1.7B"])
    emotion: str = Field(
        description="감정 분류 모델 식별자",
        examples=["jeongyoonhuh/koelectra-emotion-6class"],
    )
    tts: str = Field(description="음성 합성 모델 식별자", examples=["openbmb/VoxCPM2"])
    singing_voice: str = Field(
        description="멜로디 보존 가창 음색 변환 모델",
        examples=["Plachtaa/Seed-VC@51383efd"],
    )


class HealthReady(ApiModel):
    status: Literal["ready"] = Field(default="ready", description="요청 수신 가능 상태")
    inference_backend: Literal["real", "mock"] = Field(description="현재 추론 backend")
    queued_jobs: int = Field(description="대기 중인 추론 작업 수", ge=0)
    models: ModelConfiguration = Field(description="현재 모델 구성")
    seedvc_runtime_ready: bool = Field(description="별도 Seed-VC CPU 런타임 설치 완료 여부")


class VoiceProfileCreate(ApiModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "name": "아빠 목소리",
                    "source_kind": "current_voice",
                    "consent_owner_name": "김지훈",
                    "consent_confirmed": True,
                }
            ]
        },
    )

    name: str = Field(description="프론트에 표시할 프로필 이름", min_length=1, max_length=80)
    source_kind: Literal["pre_illness", "family_donation", "current_voice"] = Field(
        description=(
            "음성 출처. pre_illness=발병 전, family_donation=가족 기증, current_voice=현재 음성"
        )
    )
    consent_owner_name: str = Field(
        description="음성 사용에 동의한 음성 소유자 이름",
        min_length=1,
        max_length=80,
    )
    consent_confirmed: bool = Field(description="음성 소유자의 명시적 사용 동의 여부")

    @field_validator("consent_confirmed")
    @classmethod
    def require_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("음성 소유자의 명시적 동의가 필요합니다")
        return value


class VoiceSampleRead(ApiModel):
    id: str = Field(description="음성 샘플 UUID")
    prompt_text: str = Field(description="샘플에서 읽은 문장")
    duration_ms: int = Field(description="정규화된 음성 길이(ms)", ge=500)
    created_at: datetime = Field(description="샘플 등록 시각(UTC, ISO 8601)")


class VoiceProfileRead(ApiModel):
    id: str = Field(description="목소리 프로필 UUID")
    name: str = Field(description="프로필 표시 이름")
    source_kind: Literal["pre_illness", "family_donation", "current_voice"] = Field(
        description="음성 출처"
    )
    consent_owner_name: str = Field(description="동의한 음성 소유자 이름")
    status: ProfileStatusValue = Field(
        description="draft=샘플 구성 중, generating=미리듣기 생성 중, ready=사용 가능, failed=실패"
    )
    preview_version: int = Field(description="미리듣기 재생성 버전", ge=0)
    sample_count: int = Field(default=0, description="등록된 음성 샘플 수", ge=0, le=20)
    preview_url: str | None = Field(
        default=None,
        description="인증 헤더로 조회할 미리듣기 WAV 상대 URL",
    )
    created_at: datetime = Field(description="프로필 생성 시각(UTC, ISO 8601)")
    updated_at: datetime = Field(description="프로필 최종 변경 시각(UTC, ISO 8601)")


class PreviewRequest(ApiModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [{"text": "오늘도 사랑하는 우리 아이와 따뜻한 이야기를 나눌게요."}]
        },
    )

    text: str = Field(
        default="오늘도 사랑하는 우리 아이와 따뜻한 이야기를 나눌게요.",
        description="미리듣기로 합성할 한국어 문장",
        min_length=2,
        max_length=300,
    )


class BookPageCreate(ApiModel):
    page_number: int = Field(description="1부터 시작하는 페이지 번호", ge=1, le=1000)
    text: str = Field(description="VoxCPM2로 합성할 페이지 원문", min_length=1, max_length=3000)


class BookCreate(ApiModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "title": "달님 안녕",
                    "author": "담음",
                    "pages": [
                        {"page_number": 1, "text": "달님이 환하게 웃었어요."},
                        {"page_number": 2, "text": "아기도 방긋 웃었어요."},
                    ],
                }
            ]
        },
    )

    title: str = Field(description="책 제목", min_length=1, max_length=160)
    author: str | None = Field(default=None, description="저자 또는 출처", max_length=120)
    pages: list[BookPageCreate] = Field(
        description="페이지 번호와 원문 목록",
        min_length=1,
        max_length=300,
    )

    @field_validator("pages")
    @classmethod
    def unique_page_numbers(cls, pages: list[BookPageCreate]) -> list[BookPageCreate]:
        numbers = [page.page_number for page in pages]
        if len(numbers) != len(set(numbers)):
            raise ValueError("페이지 번호는 중복될 수 없습니다")
        return pages


class RecordingRead(ApiModel):
    id: str = Field(description="페이지 녹음 UUID")
    profile_id: str = Field(description="합성에 사용한 목소리 프로필 UUID")
    status: JobStatusValue = Field(description="페이지 음성 처리 상태")
    version: int = Field(description="페이지 재녹음 버전", ge=1)
    transcript: str | None = Field(
        default=None,
        description="구음장애 음성 LoRA를 적용한 Whisper STT 결과",
    )
    corrected_text: str | None = Field(default=None, description="LLM이 복원한 최종 합성 문장")
    emotion: EmotionValue | None = Field(default=None, description="한국어 감정 분류 결과")
    emotion_score: float | None = Field(
        default=None,
        description="감정 분류 신뢰도",
        ge=0,
        le=1,
    )
    original_url: str = Field(description="인증 헤더로 조회할 원본 발화 WAV 상대 URL")
    clarified_url: str | None = Field(
        default=None,
        description="처리 완료 후 생성되는 재합성 WAV 상대 URL",
    )


class BookPageRead(ApiModel):
    id: str = Field(description="페이지 UUID")
    page_number: int = Field(description="페이지 번호", ge=1)
    text: str = Field(description="페이지 원문")
    image_url: str | None = Field(default=None, description="페이지 WebP 이미지 상대 URL")
    recording: RecordingRead | None = Field(default=None, description="페이지 녹음과 합성 결과")


class BookRead(ApiModel):
    id: str = Field(description="책 UUID")
    title: str = Field(description="책 제목")
    author: str | None = Field(default=None, description="저자 또는 출처")
    pages: list[BookPageRead] = Field(description="페이지별 원문·이미지·녹음 정보")
    created_at: datetime = Field(description="책 생성 시각(UTC, ISO 8601)")
    updated_at: datetime = Field(description="책 최종 변경 시각(UTC, ISO 8601)")


class LullabyCreate(ApiModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "profile_id": "9f93bd9e-71d4-497d-9512-29c6975263f3",
                    "title": "잘 자라 우리 아가",
                    "lyrics": "잘 자라 우리 아가, 포근한 꿈을 꾸렴.",
                    "repeat_count": 3,
                    "timer_minutes": 20,
                }
            ]
        },
    )

    profile_id: str = Field(description="ready 상태인 목소리 프로필 UUID")
    title: str = Field(description="자장가 제목", min_length=1, max_length=160)
    lyrics: str = Field(
        description="부드러운 부모 음색으로 낭독할 가사",
        min_length=2,
        max_length=3000,
    )
    repeat_count: int = Field(description="프론트 재생 반복 횟수", default=1, ge=1, le=100)
    timer_minutes: int | None = Field(
        default=None,
        description="프론트에서 재생을 중단할 타이머(분)",
        ge=1,
        le=480,
    )


class LullabyRead(ApiModel):
    id: str = Field(description="자장가 UUID")
    profile_id: str = Field(description="사용한 목소리 프로필 UUID")
    title: str = Field(description="자장가 제목")
    lyrics: str = Field(description="합성한 가사")
    status: JobStatusValue = Field(description="자장가 생성 상태")
    repeat_count: int = Field(description="반복 횟수", ge=1, le=100)
    timer_minutes: int | None = Field(default=None, description="재생 타이머(분)")
    audio_url: str | None = Field(default=None, description="생성된 WAV 상대 URL")
    created_at: datetime = Field(description="생성 시각(UTC, ISO 8601)")
    updated_at: datetime = Field(description="최종 변경 시각(UTC, ISO 8601)")


class LullabyPlaybackPlanRequest(ApiModel):
    repeat_count: int | None = Field(
        default=None,
        description="이번 재생에서 사용할 반복 횟수. 생략하면 저장된 설정을 사용합니다.",
        ge=1,
        le=100,
    )
    timer_minutes: int | None = Field(
        default=None,
        description="이번 재생의 중단 타이머(분). 생략하면 저장된 설정을 사용합니다.",
        ge=1,
        le=480,
    )


class LullabyPlaybackPlan(ApiModel):
    lullaby_id: str = Field(description="자장가 UUID")
    mode: Literal["automatic"] = Field(default="automatic", description="자동 재생 모드")
    audio_url: str = Field(description="반복 재생할 WAV 상대 URL")
    repeat_count: int = Field(description="재생 반복 횟수", ge=1, le=100)
    loop: bool = Field(description="두 번 이상 반복하는지 여부")
    timer_seconds: int | None = Field(default=None, description="재생 중단 타이머(초)")
    stop_on_timer: bool = Field(description="타이머 만료 시 즉시 재생을 중단해야 하는지 여부")


class SingingSourceRead(ApiModel):
    id: str = Field(description="한국어 무반주 자장가 소스 ID")
    title: str = Field(description="소스 제목")
    description: str = Field(description="수집·생성 배경")
    lyrics: str = Field(description="한국어 가사")
    region: str = Field(description="전승 지역 또는 범위")
    duration_ms: int = Field(description="가이드 보컬 길이(ms)", ge=1)
    audio_url: str = Field(description="무반주 원본 가이드 보컬 WAV 상대 URL")
    composition_license: str = Field(description="가사·선율 이용 조건")
    recording_license: str = Field(description="가이드 녹음 이용 조건")
    attribution: str = Field(description="출처 표시 문구")


class SingingLullabyCreate(ApiModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "source_id": "jajang-jajang",
                    "profile_id": "9f93bd9e-71d4-497d-9512-29c6975263f3",
                    "repeat_count": 3,
                    "timer_minutes": 20,
                    "diffusion_steps": 10,
                    "semitone_shift": 0,
                }
            ]
        },
    )

    source_id: str = Field(
        description="카탈로그에서 선택한 무반주 자장가 ID",
        min_length=1,
        max_length=80,
        pattern=r"^[a-z0-9-]+$",
    )
    profile_id: str = Field(description="ready 상태인 목소리 프로필 UUID")
    repeat_count: int = Field(default=1, description="프론트 재생 반복 횟수", ge=1, le=100)
    timer_minutes: int | None = Field(
        default=None,
        description="프론트 재생 중단 타이머(분)",
        ge=1,
        le=480,
    )
    diffusion_steps: int | None = Field(
        default=None,
        description="Seed-VC diffusion step. 생략 시 서버 기본값, 품질 우선은 30~50",
        ge=4,
        le=50,
    )
    semitone_shift: int = Field(
        default=0,
        description="원곡 음높이 이동(반음 단위)",
        ge=-12,
        le=12,
    )


class SingingLullabyRead(ApiModel):
    id: str = Field(description="가창 자장가 변환 UUID")
    source_id: str = Field(description="선택한 카탈로그 소스 ID")
    profile_id: str = Field(description="사용한 목소리 프로필 UUID")
    title: str = Field(description="선택한 자장가 제목")
    lyrics: str = Field(description="선택한 자장가 한국어 가사")
    status: JobStatusValue = Field(description="Seed-VC 변환 상태")
    repeat_count: int = Field(description="반복 횟수", ge=1, le=100)
    timer_minutes: int | None = Field(default=None, description="재생 타이머(분)")
    diffusion_steps: int = Field(description="적용한 diffusion step", ge=4, le=50)
    semitone_shift: int = Field(description="적용한 반음 이동", ge=-12, le=12)
    audio_url: str | None = Field(default=None, description="변환 완료 WAV 상대 URL")
    created_at: datetime = Field(description="생성 시각(UTC, ISO 8601)")
    updated_at: datetime = Field(description="최종 변경 시각(UTC, ISO 8601)")


class SingingLullabyPlaybackPlan(ApiModel):
    conversion_id: str = Field(description="가창 자장가 변환 UUID")
    mode: Literal["automatic"] = Field(default="automatic", description="자동 재생 모드")
    audio_url: str = Field(description="반복 재생할 변환 WAV 상대 URL")
    repeat_count: int = Field(description="재생 반복 횟수", ge=1, le=100)
    loop: bool = Field(description="두 번 이상 반복하는지 여부")
    timer_seconds: int | None = Field(default=None, description="재생 중단 타이머(초)")
    stop_on_timer: bool = Field(description="타이머 만료 시 즉시 중단 여부")


class JobRead(ApiModel):
    id: str = Field(description="비동기 작업 UUID")
    kind: Literal[
        "recording_pipeline",
        "profile_preview",
        "lullaby_generation",
        "seedvc_lullaby_conversion",
    ] = Field(description="작업 종류")
    target_id: str = Field(description="작업 대상 리소스 UUID")
    status: JobStatusValue = Field(description="queued → running → succeeded 또는 failed")
    progress: int = Field(description="작업 진행률", ge=0, le=100)
    error_code: str | None = Field(default=None, description="실패 시 분기 처리용 오류 코드")
    error_message: str | None = Field(default=None, description="실패 시 사용자 표시용 메시지")
    created_at: datetime = Field(description="작업 생성 시각(UTC, ISO 8601)")
    updated_at: datetime = Field(description="상태 최종 변경 시각(UTC, ISO 8601)")


class JobAccepted(ApiModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "job_id": "c40c3cf0-6a96-4bcc-bc77-91de1ee28f9b",
                    "status": "queued",
                    "status_url": "/v1/jobs/c40c3cf0-6a96-4bcc-bc77-91de1ee28f9b",
                }
            ]
        },
    )

    job_id: str = Field(description="생성된 비동기 작업 UUID")
    status: Literal["queued"] = Field(default="queued", description="최초 작업 상태")
    status_url: str = Field(description="1~2초 간격으로 조회할 작업 상태 상대 URL")


class LibraryItem(ApiModel):
    id: str = Field(description="책 또는 자장가 UUID")
    kind: Literal["book", "lullaby"] = Field(description="콘텐츠 종류")
    title: str = Field(description="콘텐츠 제목")
    status: Literal[
        "draft", "processing", "partial", "ready", "queued", "running", "succeeded", "failed"
    ] = Field(description="콘텐츠 준비 상태")
    playable_url: str | None = Field(default=None, description="manifest 또는 WAV 상대 URL")
    delete_url: str = Field(description="콘텐츠를 삭제할 DELETE 요청 상대 URL")
    updated_at: datetime = Field(description="최종 변경 시각(UTC, ISO 8601)")


class PlaybackPage(ApiModel):
    page_number: int = Field(description="페이지 번호", ge=1)
    text: str = Field(description="페이지 원문")
    image_url: str | None = Field(default=None, description="페이지 이미지 상대 URL")
    original_url: str | None = Field(default=None, description="원본 발화 WAV 상대 URL")
    clarified_url: str | None = Field(default=None, description="재합성 WAV 상대 URL")
    available_sources: list[Literal["original", "clarified"]] = Field(
        description="현재 페이지에서 선택 가능한 재생 소스"
    )
    version: int | None = Field(default=None, description="페이지 녹음 버전", ge=1)


class PlaybackManifest(ApiModel):
    book_id: str = Field(description="책 UUID")
    title: str = Field(description="책 제목")
    mode: Literal["manual"] = Field(default="manual", description="페이지 수동 넘김 모드")
    pages: list[PlaybackPage] = Field(description="프리패치할 페이지별 미디어 URL")
    default_source: Literal["clarified"] = Field(
        default="clarified", description="화면 진입 시 기본 재생 소스"
    )
    source_toggle_enabled: bool = Field(default=True, description="원본·재합성 음성 토글 지원 여부")
    transition_budget_ms: int = Field(
        default=300,
        description="다음 페이지 전환의 최대 목표 지연 시간(ms)",
        ge=1,
    )
    prefetch_next: bool = Field(
        default=True,
        description="300ms 이내 전환을 위해 다음 페이지를 미리 로드해야 하는지 여부",
    )
