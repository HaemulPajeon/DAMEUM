from __future__ import annotations

import asyncio
import traceback
import uuid
from contextlib import suppress
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.inference import InferencePipeline
from app.models import (
    Job,
    JobStatus,
    Lullaby,
    PageRecording,
    ProfileStatus,
    SingingLullaby,
    VoiceProfile,
)
from app.singing import SeedVCRunner, SingingCatalog
from app.storage import MediaStore


class JobQueue:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        pipeline: InferencePipeline,
        media_store: MediaStore,
        singing_catalog: SingingCatalog,
        seedvc_runner: SeedVCRunner,
    ):
        self.settings = settings
        self.session_factory = session_factory
        self.pipeline = pipeline
        self.media_store = media_store
        self.singing_catalog = singing_catalog
        self.seedvc_runner = seedvc_runner
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=settings.max_pending_jobs)
        self.worker_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        async with self.session_factory() as session:
            await session.execute(
                update(Job)
                .where(Job.status == JobStatus.RUNNING.value)
                .values(
                    status=JobStatus.FAILED.value,
                    error_code="server_restarted",
                    error_message="서버 재시작으로 작업이 중단되었습니다. 다시 요청해 주세요.",
                )
            )
            queued = list(
                (
                    await session.scalars(
                        select(Job.id)
                        .where(Job.status == JobStatus.QUEUED.value)
                        .order_by(Job.created_at)
                        .limit(self.settings.max_pending_jobs)
                    )
                ).all()
            )
            await session.commit()
        for job_id in queued:
            self.queue.put_nowait(job_id)
        self.worker_task = asyncio.create_task(self._worker(), name="dameum-inference-worker")

    async def stop(self) -> None:
        if self.worker_task is None:
            return
        self.worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await self.worker_task
        self.pipeline.release_models()

    async def enqueue(self, job_id: str) -> None:
        try:
            self.queue.put_nowait(job_id)
        except asyncio.QueueFull as exc:
            raise RuntimeError("추론 작업 대기열이 가득 찼습니다") from exc

    async def _worker(self) -> None:
        while True:
            job_id = await self.queue.get()
            try:
                await self._run_job(job_id)
            finally:
                self.queue.task_done()

    async def _run_job(self, job_id: str) -> None:
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            if job is None or job.status != JobStatus.QUEUED.value:
                return
            job.status = JobStatus.RUNNING.value
            job.progress = 5
            await session.commit()
            kind = job.kind
        try:
            if kind == "recording_pipeline":
                await self._process_recording(job_id)
            elif kind == "profile_preview":
                await self._process_preview(job_id)
            elif kind == "lullaby_generation":
                await self._process_lullaby(job_id)
            elif kind == "seedvc_lullaby_conversion":
                await self._process_singing_lullaby(job_id)
            else:
                raise RuntimeError(f"알 수 없는 작업 종류: {kind}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._fail_job(job_id, exc)
        finally:
            self.pipeline.release_models()

    async def _process_recording(self, job_id: str) -> None:
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            recording = await session.scalar(
                select(PageRecording)
                .where(PageRecording.id == job.target_id)
                .options(
                    selectinload(PageRecording.page),
                )
            )
            if recording is None or recording.version != job.target_version:
                await self._supersede(session, job)
                return
            profile = await session.scalar(
                select(VoiceProfile)
                .where(VoiceProfile.id == recording.profile_id)
                .options(selectinload(VoiceProfile.samples))
            )
            if profile is None or len(profile.samples) < 5:
                raise RuntimeError("사용 가능한 목소리 프로필이 없습니다")
            expected_text = recording.page.text
            normalized_path = Path(recording.normalized_path)
            reference = self.media_store.profile_reference_path(profile.id)
            if not reference.is_file():
                reference = self.media_store.build_profile_reference(
                    profile.id,
                    [
                        Path(sample.normalized_path)
                        for sample in sorted(
                            profile.samples,
                            key=lambda item: item.duration_ms,
                            reverse=True,
                        )
                    ],
                )
            target_version = recording.version

        transcript = await asyncio.to_thread(
            self.pipeline.transcribe, normalized_path, expected_text
        )
        await self._progress(job_id, 30)
        # 페이지 원문이 아니라 실제 발화의 의도를 복원한 문장을 합성 입력으로 사용한다.
        corrected = await asyncio.to_thread(self.pipeline.correct_sentence, transcript)
        await self._progress(job_id, 55)
        emotion, score = await asyncio.to_thread(self.pipeline.classify_emotion, corrected)
        await self._progress(job_id, 70)
        output = (
            self.settings.data_dir / "audio" / "generated" / f"{uuid.uuid4().hex}.wav"
        ).resolve()
        await asyncio.to_thread(
            self.pipeline.synthesize, corrected, Path(reference), output, emotion
        )

        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            recording = await session.get(PageRecording, job.target_id)
            if recording is None or recording.version != target_version:
                self.media_store.delete(output)
                await self._supersede(session, job)
                return
            old_path = recording.clarified_path
            recording.transcript = transcript
            recording.corrected_text = corrected
            recording.emotion = emotion
            recording.emotion_score = f"{score:.6f}"
            recording.clarified_path = str(output)
            recording.status = JobStatus.SUCCEEDED.value
            job.status = JobStatus.SUCCEEDED.value
            job.progress = 100
            await session.commit()
        self.media_store.delete(old_path)

    async def _process_preview(self, job_id: str) -> None:
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            profile = await session.scalar(
                select(VoiceProfile)
                .where(VoiceProfile.id == job.target_id)
                .options(selectinload(VoiceProfile.samples))
            )
            if profile is None or profile.preview_version != job.target_version:
                await self._supersede(session, job)
                return
            if len(profile.samples) < 5:
                raise RuntimeError("미리듣기에는 최소 5개의 음성 샘플이 필요합니다")
            text = job.input_text or "오늘도 사랑하는 우리 아이와 따뜻한 이야기를 나눌게요."
            reference = self.media_store.build_profile_reference(
                profile.id,
                [
                    Path(sample.normalized_path)
                    for sample in sorted(
                        profile.samples,
                        key=lambda item: item.duration_ms,
                        reverse=True,
                    )
                ],
            )
            target_version = profile.preview_version
        output = (
            self.settings.data_dir / "audio" / "generated" / f"{uuid.uuid4().hex}.wav"
        ).resolve()
        await asyncio.to_thread(self.pipeline.synthesize, text, Path(reference), output, "기쁨")
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            profile = await session.get(VoiceProfile, job.target_id)
            if profile is None or profile.preview_version != target_version:
                self.media_store.delete(output)
                await self._supersede(session, job)
                return
            old_path = profile.preview_path
            profile.preview_path = str(output)
            profile.status = ProfileStatus.READY.value
            job.status = JobStatus.SUCCEEDED.value
            job.progress = 100
            await session.commit()
        self.media_store.delete(old_path)

    async def _process_lullaby(self, job_id: str) -> None:
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            lullaby = await session.get(Lullaby, job.target_id)
            if lullaby is None:
                raise RuntimeError("자장가를 찾을 수 없습니다")
            profile = await session.scalar(
                select(VoiceProfile)
                .where(VoiceProfile.id == lullaby.profile_id)
                .options(selectinload(VoiceProfile.samples))
            )
            if profile is None or len(profile.samples) < 5:
                raise RuntimeError("사용 가능한 목소리 프로필이 없습니다")
            reference = self.media_store.profile_reference_path(profile.id)
            if not reference.is_file():
                reference = self.media_store.build_profile_reference(
                    profile.id,
                    [
                        Path(sample.normalized_path)
                        for sample in sorted(
                            profile.samples,
                            key=lambda item: item.duration_ms,
                            reverse=True,
                        )
                    ],
                )
            lyrics = lullaby.lyrics
        output = (
            self.settings.data_dir / "audio" / "generated" / f"{uuid.uuid4().hex}.wav"
        ).resolve()
        await asyncio.to_thread(self.pipeline.synthesize, lyrics, Path(reference), output, "중립")
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            lullaby = await session.get(Lullaby, job.target_id)
            old_path = lullaby.audio_path
            lullaby.audio_path = str(output)
            lullaby.status = JobStatus.SUCCEEDED.value
            job.status = JobStatus.SUCCEEDED.value
            job.progress = 100
            await session.commit()
        self.media_store.delete(old_path)

    async def _process_singing_lullaby(self, job_id: str) -> None:
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            item = await session.get(SingingLullaby, job.target_id)
            if item is None:
                raise RuntimeError("가창 자장가 변환을 찾을 수 없습니다")
            source = self.singing_catalog.get(item.source_id)
            if source is None:
                raise RuntimeError("무반주 자장가 소스를 찾을 수 없습니다")
            profile = await session.scalar(
                select(VoiceProfile)
                .where(VoiceProfile.id == item.profile_id)
                .options(selectinload(VoiceProfile.samples))
            )
            if profile is None or len(profile.samples) < 5:
                raise RuntimeError("사용 가능한 목소리 프로필이 없습니다")
            reference = self.media_store.profile_reference_path(profile.id)
            if not reference.is_file():
                reference = self.media_store.build_profile_reference(
                    profile.id,
                    [
                        Path(sample.normalized_path)
                        for sample in sorted(
                            profile.samples,
                            key=lambda sample: sample.duration_ms,
                            reverse=True,
                        )
                    ],
                )
            diffusion_steps = item.diffusion_steps
            semitone_shift = item.semitone_shift
        await self._progress(job_id, 20)
        output = (
            self.settings.data_dir / "audio" / "seedvc" / "generated" / f"{uuid.uuid4().hex}.wav"
        ).resolve()
        await asyncio.to_thread(
            self.seedvc_runner.convert,
            source.audio_path,
            reference,
            output,
            diffusion_steps,
            semitone_shift,
        )
        await self._progress(job_id, 95)
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            item = await session.get(SingingLullaby, job.target_id)
            if item is None:
                self.media_store.delete(output)
                await self._supersede(session, job)
                return
            old_path = item.audio_path
            item.audio_path = str(output)
            item.status = JobStatus.SUCCEEDED.value
            job.status = JobStatus.SUCCEEDED.value
            job.progress = 100
            await session.commit()
        self.media_store.delete(old_path)

    async def _progress(self, job_id: str, progress: int) -> None:
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            if job is not None:
                job.progress = progress
                await session.commit()

    async def _fail_job(self, job_id: str, exc: Exception) -> None:
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return
            job.status = JobStatus.FAILED.value
            job.error_code = type(exc).__name__
            job.error_message = str(exc)[:1000] or "추론 작업에 실패했습니다"
            if job.kind == "recording_pipeline":
                target = await session.get(PageRecording, job.target_id)
                if target is not None and target.version == job.target_version:
                    target.status = JobStatus.FAILED.value
            elif job.kind == "profile_preview":
                target = await session.get(VoiceProfile, job.target_id)
                if target is not None and target.preview_version == job.target_version:
                    target.status = ProfileStatus.FAILED.value
            elif job.kind == "lullaby_generation":
                target = await session.get(Lullaby, job.target_id)
                if target is not None:
                    target.status = JobStatus.FAILED.value
            elif job.kind == "seedvc_lullaby_conversion":
                target = await session.get(SingingLullaby, job.target_id)
                if target is not None:
                    target.status = JobStatus.FAILED.value
            await session.commit()
        traceback.print_exception(exc)

    @staticmethod
    async def _supersede(session: AsyncSession, job: Job) -> None:
        job.status = JobStatus.FAILED.value
        job.error_code = "superseded"
        job.error_message = "더 최신 요청으로 대체된 작업입니다"
        await session.commit()
