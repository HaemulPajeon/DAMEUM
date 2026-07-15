from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VoiceProfileCreate(ApiModel):
    name: str = Field(min_length=1, max_length=80)
    source_kind: Literal["pre_illness", "family_donation", "current_voice"]
    consent_owner_name: str = Field(min_length=1, max_length=80)
    consent_confirmed: bool

    @field_validator("consent_confirmed")
    @classmethod
    def require_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("음성 소유자의 명시적 동의가 필요합니다")
        return value


class VoiceSampleRead(ApiModel):
    id: str
    prompt_text: str
    duration_ms: int
    created_at: datetime


class VoiceProfileRead(ApiModel):
    id: str
    name: str
    source_kind: str
    consent_owner_name: str
    status: str
    preview_version: int
    sample_count: int = 0
    preview_url: str | None = None
    created_at: datetime
    updated_at: datetime


class PreviewRequest(ApiModel):
    text: str = Field(
        default="오늘도 사랑하는 우리 아이와 따뜻한 이야기를 나눌게요.",
        min_length=2,
        max_length=300,
    )


class BookPageCreate(ApiModel):
    page_number: int = Field(ge=1, le=1000)
    text: str = Field(min_length=1, max_length=3000)


class BookCreate(ApiModel):
    title: str = Field(min_length=1, max_length=160)
    author: str | None = Field(default=None, max_length=120)
    pages: list[BookPageCreate] = Field(min_length=1, max_length=300)

    @field_validator("pages")
    @classmethod
    def unique_page_numbers(cls, pages: list[BookPageCreate]) -> list[BookPageCreate]:
        numbers = [page.page_number for page in pages]
        if len(numbers) != len(set(numbers)):
            raise ValueError("페이지 번호는 중복될 수 없습니다")
        return pages


class RecordingRead(ApiModel):
    id: str
    profile_id: str
    status: str
    version: int
    transcript: str | None
    corrected_text: str | None
    emotion: str | None
    emotion_score: float | None
    original_url: str
    clarified_url: str | None


class BookPageRead(ApiModel):
    id: str
    page_number: int
    text: str
    image_url: str | None
    recording: RecordingRead | None


class BookRead(ApiModel):
    id: str
    title: str
    author: str | None
    pages: list[BookPageRead]
    created_at: datetime
    updated_at: datetime


class LullabyCreate(ApiModel):
    profile_id: str
    title: str = Field(min_length=1, max_length=160)
    lyrics: str = Field(min_length=2, max_length=3000)
    repeat_count: int = Field(default=1, ge=1, le=100)
    timer_minutes: int | None = Field(default=None, ge=1, le=480)


class LullabyRead(ApiModel):
    id: str
    profile_id: str
    title: str
    lyrics: str
    status: str
    repeat_count: int
    timer_minutes: int | None
    audio_url: str | None
    created_at: datetime
    updated_at: datetime


class JobRead(ApiModel):
    id: str
    kind: str
    target_id: str
    status: str
    progress: int
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class JobAccepted(ApiModel):
    job_id: str
    status: Literal["queued"] = "queued"
    status_url: str


class LibraryItem(ApiModel):
    id: str
    kind: Literal["book", "lullaby"]
    title: str
    status: str
    playable_url: str | None
    updated_at: datetime


class PlaybackPage(ApiModel):
    page_number: int
    text: str
    image_url: str | None
    original_url: str | None
    clarified_url: str | None
    version: int | None


class PlaybackManifest(ApiModel):
    book_id: str
    title: str
    pages: list[PlaybackPage]
    prefetch_next: bool = True
