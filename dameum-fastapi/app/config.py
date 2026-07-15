from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DAMEUM_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "담음 API"
    environment: Literal["local", "test"] = "local"
    api_key: str = Field(min_length=32)
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    data_dir: Path = Path("./data")
    inference_backend: Literal["real", "mock"] = "real"
    max_audio_bytes: int = 25 * 1024 * 1024
    max_image_bytes: int = 10 * 1024 * 1024
    max_audio_seconds: int = 180
    max_pending_jobs: int = 20

    llm_base_url: str = "http://127.0.0.1:8081/v1"
    llm_api_key: str = "local-only"
    llm_model: str = "Qwen3-1.7B"
    stt_model: str = "small"
    emotion_model: str = "jeongyoonhuh/koelectra-emotion-6class"
    voxcpm_model: str = "openbmb/VoxCPM2"
    cpu_threads: int = Field(default=max(1, min(4, os.cpu_count() or 2)), ge=1, le=32)
    unload_models_after_job: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if value.startswith("["):
            return json.loads(value)
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @field_validator("cors_origins")
    @classmethod
    def local_origins_only(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            if not origin.startswith(("http://localhost:", "http://127.0.0.1:")):
                raise ValueError("로컬 HTTP origin만 허용됩니다")
        return origins

    @model_validator(mode="after")
    def reject_example_secret(self) -> Settings:
        if self.environment != "test" and self.api_key.startswith("replace-with"):
            raise ValueError("DAMEUM_API_KEY를 임의의 값으로 변경하세요")
        return self

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{(self.data_dir / 'dameum.sqlite3').resolve()}"

    def prepare_directories(self) -> None:
        for path in (
            self.data_dir,
            self.data_dir / "audio" / "original",
            self.data_dir / "audio" / "normalized",
            self.data_dir / "audio" / "profiles",
            self.data_dir / "audio" / "generated",
            self.data_dir / "images",
        ):
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(0o700)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
