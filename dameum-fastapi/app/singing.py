from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings


@dataclass(frozen=True)
class SingingSource:
    id: str
    title: str
    description: str
    lyrics: str
    region: str
    audio_path: Path
    duration_ms: int
    sha256: str
    composition_license: str
    recording_license: str
    attribution: str


class SingingCatalog:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self._items = self._load()

    def list(self) -> list[SingingSource]:
        return list(self._items.values())

    def get(self, source_id: str) -> SingingSource | None:
        return self._items.get(source_id)

    def _load(self) -> dict[str, SingingSource]:
        manifest = self.directory / "catalog.json"
        try:
            records = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("무반주 자장가 카탈로그를 읽을 수 없습니다") from exc
        if not isinstance(records, list) or not records:
            raise RuntimeError("무반주 자장가 카탈로그가 비어 있습니다")

        items: dict[str, SingingSource] = {}
        for record in records:
            try:
                source_id = str(record["id"])
                audio_path = (self.directory / str(record["audio_file"])).resolve()
                expected_sha256 = str(record["sha256"])
                if not audio_path.is_relative_to(self.directory) or audio_path.suffix != ".wav":
                    raise ValueError("허용되지 않은 카탈로그 경로입니다")
                if source_id in items or re.fullmatch(r"[a-z0-9-]+", source_id) is None:
                    raise ValueError("중복되거나 잘못된 카탈로그 ID입니다")
                if not audio_path.is_file():
                    raise ValueError("카탈로그 WAV 파일이 없습니다")
                if self._sha256(audio_path) != expected_sha256:
                    raise ValueError("카탈로그 WAV 무결성 검증에 실패했습니다")
                items[source_id] = SingingSource(
                    id=source_id,
                    title=str(record["title"]),
                    description=str(record["description"]),
                    lyrics=str(record["lyrics"]),
                    region=str(record["region"]),
                    audio_path=audio_path,
                    duration_ms=int(record["duration_ms"]),
                    sha256=expected_sha256,
                    composition_license=str(record["composition_license"]),
                    recording_license=str(record["recording_license"]),
                    attribution=str(record["attribution"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError("무반주 자장가 카탈로그가 유효하지 않습니다") from exc
        return items

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()


class SeedVCRunner:
    def __init__(self, settings: Settings):
        self.settings = settings

    def convert(
        self,
        source_path: Path,
        reference_path: Path,
        output_path: Path,
        diffusion_steps: int,
        semitone_shift: int,
    ) -> None:
        source_path = source_path.resolve(strict=True)
        reference_path = reference_path.resolve(strict=True)
        output_path = output_path.resolve()
        data_root = self.settings.data_dir.resolve()
        if not reference_path.is_relative_to(data_root) or not output_path.is_relative_to(
            data_root
        ):
            raise RuntimeError("Seed-VC 입출력 경로가 데이터 디렉터리를 벗어났습니다")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.settings.inference_backend == "mock":
            shutil.copyfile(source_path, output_path)
            output_path.chmod(0o600)
            return

        runtime_dir = self.settings.resolved_seedvc_runtime_dir
        inference_script = (runtime_dir / "inference.py").resolve()
        # venv의 Python 심볼릭 링크를 해제하면 가상환경 패키지 경로가 사라진다.
        python = self.settings.seedvc_python_path
        if not self.settings.seedvc_runtime_ready:
            raise RuntimeError(
                "Seed-VC 런타임이 없습니다. uv run python -m scripts.setup_seedvc를 실행하세요"
            )
        self._verify_runtime(runtime_dir)
        bridge = (self.settings.project_dir / "scripts" / "seedvc_cpu_bridge.py").resolve()
        work_dir = (
            self.settings.data_dir / "audio" / "seedvc" / "work" / uuid.uuid4().hex
        ).resolve()
        work_dir.mkdir(parents=True, mode=0o700)
        environment = os.environ.copy()
        for name in list(environment):
            if name.startswith(("DAMEUM_", "OPENAI_")) or name == "HF_TOKEN":
                environment.pop(name, None)
        environment.update(
            {
                "CUDA_VISIBLE_DEVICES": "-1",
                "PYTHONUTF8": "1",
                "OMP_NUM_THREADS": str(self.settings.cpu_threads),
                "MKL_NUM_THREADS": str(self.settings.cpu_threads),
            }
        )
        try:
            chunks = self._split_source(source_path, work_dir)
            converted = []
            for index, chunk in enumerate(chunks):
                chunk_output = work_dir / f"output-{index:03d}"
                chunk_output.mkdir(mode=0o700)
                command = [
                    str(python),
                    str(bridge),
                    str(inference_script),
                    "--source",
                    str(chunk),
                    "--target",
                    str(reference_path),
                    "--output",
                    str(chunk_output),
                    "--diffusion-steps",
                    str(diffusion_steps),
                    "--length-adjust",
                    "1.0",
                    "--inference-cfg-rate",
                    "0.7",
                    "--f0-condition",
                    "True",
                    "--auto-f0-adjust",
                    "False",
                    "--semi-tone-shift",
                    str(semitone_shift),
                    "--fp16",
                    "False",
                ]
                # 고정된 bridge와 검증된 로컬 경로만 shell 없이 전달한다.
                completed = subprocess.run(  # noqa: S603
                    command,
                    cwd=runtime_dir,
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.settings.seedvc_timeout_seconds,
                )
                if completed.returncode != 0:
                    error = (completed.stderr or completed.stdout or "Seed-VC 실행 실패")[-2000:]
                    raise RuntimeError(f"Seed-VC 변환에 실패했습니다: {error}")
                generated = list(chunk_output.glob("*.wav"))
                if len(generated) != 1:
                    raise RuntimeError("Seed-VC 결과 WAV를 찾을 수 없습니다")
                converted.append(generated[0])
            self._join_chunks(converted, output_path)
            output_path.chmod(0o600)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Seed-VC CPU 변환 제한 시간을 초과했습니다") from exc
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def _verify_runtime(self, runtime_dir: Path) -> None:
        git = shutil.which("git")
        if git is None:
            raise RuntimeError("Seed-VC 런타임 검증에 필요한 Git을 찾을 수 없습니다")
        revision = subprocess.run(  # noqa: S603
            [git, "-C", str(runtime_dir), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        changes = subprocess.run(  # noqa: S603
            [git, "-C", str(runtime_dir), "status", "--porcelain", "--untracked-files=no"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if (
            revision.returncode != 0
            or revision.stdout.strip() != self.settings.seedvc_commit
            or changes.returncode != 0
            or changes.stdout.strip()
        ):
            raise RuntimeError("Seed-VC 런타임 커밋 또는 작업 트리 무결성 검증에 실패했습니다")

    @staticmethod
    def _split_source(source_path: Path, work_dir: Path) -> list[Path]:
        import numpy as np
        import soundfile as sf

        audio, sample_rate = sf.read(source_path, dtype="float32", always_2d=False)
        if audio.ndim != 1 or sample_rate < 16000:
            raise RuntimeError("Seed-VC 원곡은 mono WAV여야 합니다")
        maximum = sample_rate * 3
        if len(audio) <= maximum:
            return [source_path]
        chunks = []
        start = 0
        while start < len(audio):
            target = min(start + maximum, len(audio))
            if target < len(audio):
                search_start = max(start + sample_rate, target - int(sample_rate * 0.6))
                search_end = min(len(audio), target + int(sample_rate * 0.2))
                window = max(1, int(sample_rate * 0.02))
                energy = np.convolve(
                    np.abs(audio[search_start:search_end]),
                    np.ones(window, dtype=np.float32) / window,
                    mode="same",
                )
                target = search_start + int(np.argmin(energy))
            chunk_path = work_dir / f"source-{len(chunks):03d}.wav"
            sf.write(chunk_path, audio[start:target], sample_rate, subtype="PCM_16")
            chunks.append(chunk_path)
            start = target
        return chunks

    @staticmethod
    def _join_chunks(chunks: list[Path], output_path: Path) -> None:
        import numpy as np
        import soundfile as sf

        if not chunks:
            raise RuntimeError("결합할 Seed-VC 결과가 없습니다")
        parts = []
        sample_rate = 0
        for chunk in chunks:
            audio, current_rate = sf.read(chunk, dtype="float32", always_2d=False)
            if audio.ndim != 1 or (sample_rate and current_rate != sample_rate):
                raise RuntimeError("Seed-VC 결과 WAV 형식이 일치하지 않습니다")
            sample_rate = current_rate
            parts.append(audio)
        joined = parts[0]
        for part in parts[1:]:
            overlap = min(int(sample_rate * 0.02), len(joined), len(part))
            if overlap:
                fade_out = np.linspace(1, 0, overlap, dtype=np.float32)
                fade_in = np.linspace(0, 1, overlap, dtype=np.float32)
                joined[-overlap:] = joined[-overlap:] * fade_out + part[:overlap] * fade_in
                joined = np.concatenate((joined, part[overlap:]))
            else:
                joined = np.concatenate((joined, part))
        sf.write(output_path, joined, sample_rate, subtype="PCM_16")
