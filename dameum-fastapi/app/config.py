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
    stt_model: str = "openai/whisper-small"
    stt_adapter_dir: Path = Path("./artifacts/stt/whisper-small-lora-dysarthria")
    stt_adapter_sha256: str = Field(
        default="9772a95bfd1d77716ddae060790a6c40ad80f65a31d551caf7ce12f5a242ecbe",
        pattern=r"^[0-9a-f]{64}$",
    )
    emotion_model: str = "jeongyoonhuh/koelectra-emotion-6class"
    voxcpm_model: str = "openbmb/VoxCPM2"
    seedvc_runtime_dir: Path = Path("./.runtime/seed-vc")
    seedvc_commit: str = "51383efd921027683c89e5348211d93ff12ac2a8"
    seedvc_diffusion_steps: int = Field(default=10, ge=4, le=50)
    seedvc_timeout_seconds: int = Field(default=3600, ge=60, le=7200)
    lullaby_catalog_dir: Path = Path("./assets/lullabies")
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

    @property
    def resolved_stt_adapter_dir(self) -> Path:
        if self.stt_adapter_dir.is_absolute():
            return self.stt_adapter_dir.resolve()
        project_dir = Path(__file__).resolve().parents[1]
        return (project_dir / self.stt_adapter_dir).resolve()

    @property
    def project_dir(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def resolve_project_path(self, value: Path) -> Path:
        if value.is_absolute():
            return value.resolve()
        return (self.project_dir / value).resolve()

    @property
    def resolved_seedvc_runtime_dir(self) -> Path:
        return self.resolve_project_path(self.seedvc_runtime_dir)

    @property
    def resolved_lullaby_catalog_dir(self) -> Path:
        return self.resolve_project_path(self.lullaby_catalog_dir)

    @property
    def seedvc_python_path(self) -> Path:
        if os.name == "nt":
            return self.resolved_seedvc_runtime_dir / ".venv" / "Scripts" / "python.exe"
        return self.resolved_seedvc_runtime_dir / ".venv" / "bin" / "python"

    @property
    def seedvc_runtime_ready(self) -> bool:
        return (
            self.resolved_seedvc_runtime_dir / "inference.py"
        ).is_file() and self.seedvc_python_path.is_file()

    def prepare_directories(self) -> None:
        for path in (
            self.data_dir,
            self.data_dir / "audio" / "original",
            self.data_dir / "audio" / "normalized",
            self.data_dir / "audio" / "profiles",
            self.data_dir / "audio" / "generated",
            self.data_dir / "audio" / "seedvc" / "generated",
            self.data_dir / "audio" / "seedvc" / "work",
            self.data_dir / "images",
        ):
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(0o700)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
