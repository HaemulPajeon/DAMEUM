from __future__ import annotations

import hashlib
import io
import uuid
import wave
from dataclasses import dataclass
from pathlib import Path

import av
from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError


@dataclass(frozen=True)
class StoredAudio:
    original_path: Path
    normalized_path: Path
    media_type: str
    sha256: str
    size_bytes: int
    duration_ms: int


class MediaStore:
    def __init__(
        self,
        data_dir: Path,
        max_audio_bytes: int,
        max_image_bytes: int,
        max_seconds: int,
    ):
        self.data_dir = data_dir.resolve()
        self.max_audio_bytes = max_audio_bytes
        self.max_image_bytes = max_image_bytes
        self.max_seconds = max_seconds

    async def save_audio(self, upload: UploadFile) -> StoredAudio:
        raw, sha256 = await self._read_limited(upload, self.max_audio_bytes)
        self._validate_audio_signature(raw)
        token = uuid.uuid4().hex
        original = self.data_dir / "audio" / "original" / f"{token}.bin"
        normalized = self.data_dir / "audio" / "normalized" / f"{token}.wav"
        original.write_bytes(raw)
        original.chmod(0o600)
        try:
            duration_ms = self._normalize_audio(original, normalized)
        except Exception as exc:
            original.unlink(missing_ok=True)
            normalized.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_audio", "message": "오디오를 디코딩할 수 없습니다"},
            ) from exc
        if duration_ms < 500 or duration_ms > self.max_seconds * 1000:
            original.unlink(missing_ok=True)
            normalized.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "invalid_audio_duration",
                    "message": f"오디오는 0.5초 이상 {self.max_seconds}초 이하여야 합니다",
                },
            )
        return StoredAudio(
            original_path=original,
            normalized_path=normalized,
            media_type=upload.content_type or "application/octet-stream",
            sha256=sha256,
            size_bytes=len(raw),
            duration_ms=duration_ms,
        )

    async def save_image(self, upload: UploadFile) -> Path:
        raw, _ = await self._read_limited(upload, self.max_image_bytes)
        try:
            with Image.open(io.BytesIO(raw)) as source:
                source.verify()
            with Image.open(io.BytesIO(raw)) as source:
                if source.width * source.height > 40_000_000:
                    raise ValueError("image too large")
                image = source.convert("RGB")
                target = self.data_dir / "images" / f"{uuid.uuid4().hex}.webp"
                # 메타데이터를 제거해 위치·기기 정보가 남지 않게 한다.
                image.save(target, "WEBP", quality=88, method=6)
                target.chmod(0o600)
                return target
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_image", "message": "유효한 이미지가 아닙니다"},
            ) from exc

    def profile_reference_path(self, profile_id: str) -> Path:
        token = uuid.UUID(profile_id).hex
        return self.data_dir / "audio" / "profiles" / f"{token}.wav"

    def build_profile_reference(
        self,
        profile_id: str,
        normalized_paths: list[Path],
        max_seconds: int = 30,
    ) -> Path:
        if not normalized_paths:
            raise ValueError("목소리 프로필에 음성 샘플이 없습니다")
        target = self.profile_reference_path(profile_id)
        temporary = target.with_suffix(".tmp.wav")
        max_frames = max_seconds * 16000
        silence = b"\x00\x00" * 1920
        written_frames = 0
        try:
            with wave.open(str(temporary), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                for path in normalized_paths:
                    with wave.open(str(path), "rb") as source:
                        if (
                            source.getnchannels() != 1
                            or source.getsampwidth() != 2
                            or source.getframerate() != 16000
                        ):
                            raise ValueError("정규화되지 않은 프로필 음성 샘플입니다")
                        remaining = max_frames - written_frames
                        if remaining <= 0:
                            break
                        frame_count = min(source.getnframes(), remaining)
                        output.writeframes(source.readframes(frame_count))
                        written_frames += frame_count
                    if written_frames < max_frames:
                        silence_frames = min(len(silence) // 2, max_frames - written_frames)
                        output.writeframes(silence[: silence_frames * 2])
                        written_frames += silence_frames
            if written_frames < 16000:
                raise ValueError("프로필 참조 음성은 최소 1초 이상이어야 합니다")
            temporary.replace(target)
            target.chmod(0o600)
            return target
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def delete(self, value: str | Path | None) -> None:
        if value is None:
            return
        path = Path(value).resolve()
        if path.is_relative_to(self.data_dir):
            path.unlink(missing_ok=True)

    async def _read_limited(self, upload: UploadFile, limit: int) -> tuple[bytes, str]:
        chunks: list[bytes] = []
        digest = hashlib.sha256()
        size = 0
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail={"code": "file_too_large", "message": "업로드 허용 크기를 초과했습니다"},
                )
            digest.update(chunk)
            chunks.append(chunk)
        return b"".join(chunks), digest.hexdigest()

    @staticmethod
    def _validate_audio_signature(raw: bytes) -> None:
        signatures = (
            raw.startswith(b"RIFF") and raw[8:12] == b"WAVE",
            raw.startswith(b"fLaC"),
            raw.startswith(b"OggS"),
            raw.startswith(b"ID3"),
            len(raw) > 2 and raw[0] == 0xFF and raw[1] & 0xE0 == 0xE0,
            len(raw) > 12 and raw[4:8] == b"ftyp",
            raw.startswith(b"\x1aE\xdf\xa3"),
        )
        if not raw or not any(signatures):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={"code": "unsupported_audio", "message": "지원하지 않는 오디오 형식입니다"},
            )

    def _normalize_audio(self, source: Path, target: Path) -> int:
        with av.open(str(source)) as container:
            if not container.streams.audio:
                raise ValueError("audio stream missing")
            input_stream = container.streams.audio[0]
            resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
            with av.open(str(target), mode="w", format="wav") as output:
                output_stream = output.add_stream("pcm_s16le", rate=16000)
                output_stream.layout = "mono"
                samples = 0
                for frame in container.decode(input_stream):
                    for converted in resampler.resample(frame):
                        samples += converted.samples
                        if samples > self.max_seconds * 16000:
                            raise ValueError("audio duration exceeded")
                        output.mux(output_stream.encode(converted))
                for converted in resampler.resample(None):
                    samples += converted.samples
                    output.mux(output_stream.encode(converted))
                output.mux(output_stream.encode(None))
        target.chmod(0o600)
        return round(samples / 16000 * 1000)
