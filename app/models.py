from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin


def new_id() -> str:
    return str(uuid.uuid4())


class SourceKind(enum.StrEnum):
    PRE_ILLNESS = "pre_illness"
    FAMILY_DONATION = "family_donation"
    CURRENT_VOICE = "current_voice"


class ProfileStatus(enum.StrEnum):
    DRAFT = "draft"
    READY = "ready"
    GENERATING = "generating"
    FAILED = "failed"


class JobStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class VoiceProfile(TimestampMixin, Base):
    __tablename__ = "voice_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80))
    source_kind: Mapped[str] = mapped_column(String(32))
    consent_owner_name: Mapped[str] = mapped_column(String(80))
    consent_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default=ProfileStatus.DRAFT.value)
    preview_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    preview_version: Mapped[int] = mapped_column(Integer, default=0)

    samples: Mapped[list[VoiceSample]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", lazy="selectin"
    )


class VoiceSample(TimestampMixin, Base):
    __tablename__ = "voice_samples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("voice_profiles.id", ondelete="CASCADE"), index=True
    )
    prompt_text: Mapped[str] = mapped_column(Text)
    original_path: Mapped[str] = mapped_column(Text)
    normalized_path: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(80))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)

    profile: Mapped[VoiceProfile] = relationship(back_populates="samples")


class Book(TimestampMixin, Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(160))
    author: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pages: Mapped[list[BookPage]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="BookPage.page_number",
    )


class BookPage(TimestampMixin, Base):
    __tablename__ = "book_pages"
    __table_args__ = (UniqueConstraint("book_id", "page_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    book: Mapped[Book] = relationship(back_populates="pages")
    recording: Mapped[PageRecording | None] = relationship(
        back_populates="page", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )


class PageRecording(TimestampMixin, Base):
    __tablename__ = "page_recordings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    page_id: Mapped[str] = mapped_column(
        ForeignKey("book_pages.id", ondelete="CASCADE"), unique=True, index=True
    )
    profile_id: Mapped[str] = mapped_column(ForeignKey("voice_profiles.id", ondelete="RESTRICT"))
    original_path: Mapped[str] = mapped_column(Text)
    normalized_path: Mapped[str] = mapped_column(Text)
    clarified_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    emotion: Mapped[str | None] = mapped_column(String(40), nullable=True)
    emotion_score: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default=JobStatus.QUEUED.value)
    version: Mapped[int] = mapped_column(Integer, default=1)

    page: Mapped[BookPage] = relationship(back_populates="recording")


class Lullaby(TimestampMixin, Base):
    __tablename__ = "lullabies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(ForeignKey("voice_profiles.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(160))
    lyrics: Mapped[str] = mapped_column(Text)
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default=JobStatus.QUEUED.value)
    repeat_count: Mapped[int] = mapped_column(Integer, default=1)
    timer_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    target_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default=JobStatus.QUEUED.value)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
