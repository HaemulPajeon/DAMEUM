from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import session_dependency
from app.models import (
    Book,
    BookPage,
    Job,
    JobStatus,
    Lullaby,
    PageRecording,
    ProfileStatus,
    VoiceProfile,
    VoiceSample,
)
from app.schemas import (
    BookCreate,
    BookPageRead,
    BookRead,
    JobAccepted,
    JobRead,
    LibraryItem,
    LullabyCreate,
    LullabyRead,
    PlaybackManifest,
    PlaybackPage,
    PreviewRequest,
    RecordingRead,
    VoiceProfileCreate,
    VoiceProfileRead,
    VoiceSampleRead,
)
from app.security import require_api_key

router = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)])


def not_found(resource: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "not_found", "message": f"{resource}을(를) 찾을 수 없습니다"},
    )


def profile_read(profile: VoiceProfile) -> VoiceProfileRead:
    return VoiceProfileRead(
        id=profile.id,
        name=profile.name,
        source_kind=profile.source_kind,
        consent_owner_name=profile.consent_owner_name,
        status=profile.status,
        preview_version=profile.preview_version,
        sample_count=len(profile.samples),
        preview_url=(
            f"/v1/voice-profiles/{profile.id}/preview/audio" if profile.preview_path else None
        ),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def recording_read(recording: PageRecording, book_id: str, page_number: int) -> RecordingRead:
    return RecordingRead(
        id=recording.id,
        profile_id=recording.profile_id,
        status=recording.status,
        version=recording.version,
        transcript=recording.transcript,
        corrected_text=recording.corrected_text,
        emotion=recording.emotion,
        emotion_score=float(recording.emotion_score) if recording.emotion_score else None,
        original_url=f"/v1/books/{book_id}/pages/{page_number}/audio?source=original",
        clarified_url=(
            f"/v1/books/{book_id}/pages/{page_number}/audio?source=clarified"
            if recording.clarified_path
            else None
        ),
    )


def page_read(page: BookPage) -> BookPageRead:
    return BookPageRead(
        id=page.id,
        page_number=page.page_number,
        text=page.text,
        image_url=(
            f"/v1/books/{page.book_id}/pages/{page.page_number}/image" if page.image_path else None
        ),
        recording=(
            recording_read(page.recording, page.book_id, page.page_number)
            if page.recording
            else None
        ),
    )


def book_read(book: Book) -> BookRead:
    return BookRead(
        id=book.id,
        title=book.title,
        author=book.author,
        pages=[page_read(page) for page in book.pages],
        created_at=book.created_at,
        updated_at=book.updated_at,
    )


def lullaby_read(lullaby: Lullaby) -> LullabyRead:
    return LullabyRead(
        id=lullaby.id,
        profile_id=lullaby.profile_id,
        title=lullaby.title,
        lyrics=lullaby.lyrics,
        status=lullaby.status,
        repeat_count=lullaby.repeat_count,
        timer_minutes=lullaby.timer_minutes,
        audio_url=f"/v1/lullabies/{lullaby.id}/audio" if lullaby.audio_path else None,
        created_at=lullaby.created_at,
        updated_at=lullaby.updated_at,
    )


async def get_profile_with_samples(session: AsyncSession, profile_id: str) -> VoiceProfile:
    profile = await session.scalar(
        select(VoiceProfile)
        .where(VoiceProfile.id == profile_id)
        .options(selectinload(VoiceProfile.samples))
    )
    if profile is None:
        raise not_found("목소리 프로필")
    return profile


async def get_book_with_pages(session: AsyncSession, book_id: str) -> Book:
    book = await session.scalar(
        select(Book)
        .where(Book.id == book_id)
        .options(selectinload(Book.pages).selectinload(BookPage.recording))
    )
    if book is None:
        raise not_found("책")
    return book


async def get_page(session: AsyncSession, book_id: str, page_number: int) -> BookPage:
    page = await session.scalar(
        select(BookPage)
        .where(BookPage.book_id == book_id, BookPage.page_number == page_number)
        .options(selectinload(BookPage.recording))
    )
    if page is None:
        raise not_found("페이지")
    return page


async def enqueue_or_fail(request: Request, session: AsyncSession, job: Job) -> None:
    try:
        await request.app.state.job_queue.enqueue(job.id)
    except RuntimeError as exc:
        job.status = JobStatus.FAILED.value
        job.error_code = "queue_full"
        job.error_message = str(exc)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "queue_full", "message": "추론 작업 대기열이 가득 찼습니다"},
            headers={"Retry-After": "30"},
        ) from exc


def job_accepted(job: Job) -> JobAccepted:
    return JobAccepted(job_id=job.id, status_url=f"/v1/jobs/{job.id}")


def file_response(path_value: str | None, media_type: str) -> FileResponse:
    if not path_value:
        raise not_found("미디어")
    path = Path(path_value)
    if not path.is_file():
        raise not_found("미디어")
    stat = path.stat()
    etag = f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'
    return FileResponse(
        path,
        media_type=media_type,
        headers={
            "Cache-Control": "private, max-age=3600",
            "ETag": etag,
            "Accept-Ranges": "bytes",
        },
    )


@router.post("/voice-profiles", response_model=VoiceProfileRead, status_code=201)
async def create_voice_profile(
    payload: VoiceProfileCreate,
    session: AsyncSession = Depends(session_dependency),
) -> VoiceProfileRead:
    profile = VoiceProfile(**payload.model_dump())
    session.add(profile)
    await session.commit()
    await session.refresh(profile, attribute_names=["samples"])
    return profile_read(profile)


@router.get("/voice-profiles", response_model=list[VoiceProfileRead])
async def list_voice_profiles(
    session: AsyncSession = Depends(session_dependency),
) -> list[VoiceProfileRead]:
    profiles = (
        await session.scalars(
            select(VoiceProfile)
            .options(selectinload(VoiceProfile.samples))
            .order_by(VoiceProfile.created_at.desc())
        )
    ).all()
    return [profile_read(profile) for profile in profiles]


@router.get("/voice-profiles/{profile_id}", response_model=VoiceProfileRead)
async def get_voice_profile(
    profile_id: str, session: AsyncSession = Depends(session_dependency)
) -> VoiceProfileRead:
    return profile_read(await get_profile_with_samples(session, profile_id))


@router.post(
    "/voice-profiles/{profile_id}/samples",
    response_model=VoiceSampleRead,
    status_code=201,
)
async def add_voice_sample(
    request: Request,
    profile_id: str,
    prompt_text: str = Form(min_length=1, max_length=500),
    audio: UploadFile = File(),
    session: AsyncSession = Depends(session_dependency),
) -> VoiceSampleRead:
    profile = await get_profile_with_samples(session, profile_id)
    if len(profile.samples) >= 20:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "sample_limit", "message": "샘플은 최대 20개까지 등록할 수 있습니다"},
        )
    stored = await request.app.state.media_store.save_audio(audio)
    old_preview = profile.preview_path
    sample = VoiceSample(
        profile_id=profile.id,
        prompt_text=prompt_text.strip(),
        original_path=str(stored.original_path),
        normalized_path=str(stored.normalized_path),
        media_type=stored.media_type,
        sha256=stored.sha256,
        size_bytes=stored.size_bytes,
        duration_ms=stored.duration_ms,
    )
    profile.status = ProfileStatus.DRAFT.value
    profile.preview_path = None
    session.add(sample)
    await session.commit()
    await session.refresh(sample)
    request.app.state.media_store.delete(old_preview)
    return VoiceSampleRead.model_validate(sample)


@router.get("/voice-profiles/{profile_id}/samples", response_model=list[VoiceSampleRead])
async def list_voice_samples(
    profile_id: str, session: AsyncSession = Depends(session_dependency)
) -> list[VoiceSampleRead]:
    profile = await get_profile_with_samples(session, profile_id)
    return [VoiceSampleRead.model_validate(sample) for sample in profile.samples]


@router.delete("/voice-profiles/{profile_id}/samples/{sample_id}", status_code=204)
async def delete_voice_sample(
    request: Request,
    profile_id: str,
    sample_id: str,
    session: AsyncSession = Depends(session_dependency),
) -> None:
    sample = await session.scalar(
        select(VoiceSample).where(VoiceSample.id == sample_id, VoiceSample.profile_id == profile_id)
    )
    if sample is None:
        raise not_found("음성 샘플")
    paths = (sample.original_path, sample.normalized_path)
    profile = await session.get(VoiceProfile, profile_id)
    old_preview = profile.preview_path
    await session.delete(sample)
    profile.status = ProfileStatus.DRAFT.value
    profile.preview_path = None
    await session.commit()
    for path in paths:
        request.app.state.media_store.delete(path)
    request.app.state.media_store.delete(old_preview)


@router.delete("/voice-profiles/{profile_id}", status_code=204)
async def delete_voice_profile(
    request: Request,
    profile_id: str,
    session: AsyncSession = Depends(session_dependency),
) -> None:
    profile = await get_profile_with_samples(session, profile_id)
    recording_count = await session.scalar(
        select(func.count(PageRecording.id)).where(PageRecording.profile_id == profile_id)
    )
    lullaby_count = await session.scalar(
        select(func.count(Lullaby.id)).where(Lullaby.profile_id == profile_id)
    )
    if recording_count or lullaby_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "profile_in_use",
                "message": "이 프로필을 사용한 책 녹음과 자장가를 먼저 삭제해야 합니다",
            },
        )
    paths: list[str | None] = [profile.preview_path]
    for sample in profile.samples:
        paths.extend([sample.original_path, sample.normalized_path])
    await session.delete(profile)
    await session.commit()
    for path in paths:
        request.app.state.media_store.delete(path)


@router.post(
    "/voice-profiles/{profile_id}/preview",
    response_model=JobAccepted,
    status_code=202,
)
async def generate_profile_preview(
    request: Request,
    profile_id: str,
    payload: PreviewRequest,
    session: AsyncSession = Depends(session_dependency),
) -> JobAccepted:
    profile = await get_profile_with_samples(session, profile_id)
    if not 5 <= len(profile.samples) <= 20:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "insufficient_samples", "message": "샘플 5~20개를 등록해야 합니다"},
        )
    profile.preview_version += 1
    profile.status = ProfileStatus.GENERATING.value
    job = Job(
        kind="profile_preview",
        target_id=profile.id,
        target_version=profile.preview_version,
        input_text=payload.text,
    )
    session.add(job)
    await session.commit()
    await enqueue_or_fail(request, session, job)
    return job_accepted(job)


@router.get("/voice-profiles/{profile_id}/preview/audio")
async def get_profile_preview_audio(
    profile_id: str, session: AsyncSession = Depends(session_dependency)
) -> FileResponse:
    profile = await session.get(VoiceProfile, profile_id)
    if profile is None:
        raise not_found("목소리 프로필")
    return file_response(profile.preview_path, "audio/wav")


@router.post("/books", response_model=BookRead, status_code=201)
async def create_book(
    payload: BookCreate, session: AsyncSession = Depends(session_dependency)
) -> BookRead:
    book = Book(title=payload.title, author=payload.author)
    book.pages = [BookPage(**page.model_dump()) for page in payload.pages]
    session.add(book)
    await session.commit()
    return book_read(await get_book_with_pages(session, book.id))


@router.get("/books", response_model=list[BookRead])
async def list_books(session: AsyncSession = Depends(session_dependency)) -> list[BookRead]:
    books = (
        (
            await session.scalars(
                select(Book)
                .options(selectinload(Book.pages).selectinload(BookPage.recording))
                .order_by(Book.updated_at.desc())
            )
        )
        .unique()
        .all()
    )
    return [book_read(book) for book in books]


@router.get("/books/{book_id}", response_model=BookRead)
async def get_book(book_id: str, session: AsyncSession = Depends(session_dependency)) -> BookRead:
    return book_read(await get_book_with_pages(session, book_id))


@router.delete("/books/{book_id}", status_code=204)
async def delete_book(
    request: Request,
    book_id: str,
    session: AsyncSession = Depends(session_dependency),
) -> None:
    book = await get_book_with_pages(session, book_id)
    paths: list[str | None] = []
    for page in book.pages:
        paths.append(page.image_path)
        if page.recording:
            paths.extend(
                [
                    page.recording.original_path,
                    page.recording.normalized_path,
                    page.recording.clarified_path,
                ]
            )
    await session.delete(book)
    await session.commit()
    for path in paths:
        request.app.state.media_store.delete(path)


@router.put("/books/{book_id}/pages/{page_number}/image", status_code=204)
async def put_page_image(
    request: Request,
    book_id: str,
    page_number: int,
    image: UploadFile = File(),
    session: AsyncSession = Depends(session_dependency),
) -> None:
    page = await get_page(session, book_id, page_number)
    new_path = await request.app.state.media_store.save_image(image)
    old_path = page.image_path
    page.image_path = str(new_path)
    await session.commit()
    request.app.state.media_store.delete(old_path)


@router.get("/books/{book_id}/pages/{page_number}/image")
async def get_page_image(
    book_id: str,
    page_number: int,
    session: AsyncSession = Depends(session_dependency),
) -> FileResponse:
    page = await get_page(session, book_id, page_number)
    return file_response(page.image_path, "image/webp")


@router.put(
    "/books/{book_id}/pages/{page_number}/recording",
    response_model=JobAccepted,
    status_code=202,
)
async def put_page_recording(
    request: Request,
    book_id: str,
    page_number: int,
    profile_id: str = Form(),
    audio: UploadFile = File(),
    session: AsyncSession = Depends(session_dependency),
) -> JobAccepted:
    page = await get_page(session, book_id, page_number)
    profile = await get_profile_with_samples(session, profile_id)
    if profile.status != ProfileStatus.READY.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "profile_not_ready",
                "message": "미리듣기로 확인을 마친 목소리 프로필이 필요합니다",
            },
        )
    stored = await request.app.state.media_store.save_audio(audio)
    old_paths: tuple[str | None, ...] = ()
    if page.recording:
        recording = page.recording
        old_paths = (
            recording.original_path,
            recording.normalized_path,
            recording.clarified_path,
        )
        recording.profile_id = profile_id
        recording.original_path = str(stored.original_path)
        recording.normalized_path = str(stored.normalized_path)
        recording.clarified_path = None
        recording.transcript = None
        recording.corrected_text = None
        recording.emotion = None
        recording.emotion_score = None
        recording.status = JobStatus.QUEUED.value
        recording.version += 1
    else:
        recording = PageRecording(
            page_id=page.id,
            profile_id=profile_id,
            original_path=str(stored.original_path),
            normalized_path=str(stored.normalized_path),
        )
        session.add(recording)
    await session.flush()
    job = Job(
        kind="recording_pipeline",
        target_id=recording.id,
        target_version=recording.version,
    )
    session.add(job)
    await session.commit()
    for path in old_paths:
        request.app.state.media_store.delete(path)
    await enqueue_or_fail(request, session, job)
    return job_accepted(job)


@router.get("/books/{book_id}/pages/{page_number}/audio")
async def get_page_audio(
    book_id: str,
    page_number: int,
    source: str = "clarified",
    session: AsyncSession = Depends(session_dependency),
) -> FileResponse:
    if source not in {"original", "clarified"}:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_source", "message": "source는 original 또는 clarified입니다"},
        )
    page = await get_page(session, book_id, page_number)
    if page.recording is None:
        raise not_found("페이지 녹음")
    path = page.recording.normalized_path if source == "original" else page.recording.clarified_path
    return file_response(path, "audio/wav")


@router.get("/books/{book_id}/playback-manifest", response_model=PlaybackManifest)
async def get_playback_manifest(
    book_id: str, session: AsyncSession = Depends(session_dependency)
) -> PlaybackManifest:
    book = await get_book_with_pages(session, book_id)
    pages = []
    for page in book.pages:
        recording = page.recording
        pages.append(
            PlaybackPage(
                page_number=page.page_number,
                text=page.text,
                image_url=(
                    f"/v1/books/{book.id}/pages/{page.page_number}/image"
                    if page.image_path
                    else None
                ),
                original_url=(
                    f"/v1/books/{book.id}/pages/{page.page_number}/audio?source=original"
                    if recording
                    else None
                ),
                clarified_url=(
                    f"/v1/books/{book.id}/pages/{page.page_number}/audio?source=clarified"
                    if recording and recording.clarified_path
                    else None
                ),
                version=recording.version if recording else None,
            )
        )
    return PlaybackManifest(book_id=book.id, title=book.title, pages=pages)


@router.post("/lullabies", response_model=JobAccepted, status_code=202)
async def create_lullaby(
    request: Request,
    payload: LullabyCreate,
    session: AsyncSession = Depends(session_dependency),
) -> JobAccepted:
    profile = await get_profile_with_samples(session, payload.profile_id)
    if profile.status != ProfileStatus.READY.value:
        raise HTTPException(
            status_code=409,
            detail={"code": "profile_not_ready", "message": "준비된 목소리 프로필이 필요합니다"},
        )
    lullaby = Lullaby(**payload.model_dump())
    session.add(lullaby)
    await session.flush()
    job = Job(kind="lullaby_generation", target_id=lullaby.id)
    session.add(job)
    await session.commit()
    await enqueue_or_fail(request, session, job)
    return job_accepted(job)


@router.get("/lullabies", response_model=list[LullabyRead])
async def list_lullabies(
    session: AsyncSession = Depends(session_dependency),
) -> list[LullabyRead]:
    items = (await session.scalars(select(Lullaby).order_by(Lullaby.updated_at.desc()))).all()
    return [lullaby_read(item) for item in items]


@router.get("/lullabies/{lullaby_id}", response_model=LullabyRead)
async def get_lullaby(
    lullaby_id: str, session: AsyncSession = Depends(session_dependency)
) -> LullabyRead:
    lullaby = await session.get(Lullaby, lullaby_id)
    if lullaby is None:
        raise not_found("자장가")
    return lullaby_read(lullaby)


@router.get("/lullabies/{lullaby_id}/audio")
async def get_lullaby_audio(
    lullaby_id: str, session: AsyncSession = Depends(session_dependency)
) -> FileResponse:
    lullaby = await session.get(Lullaby, lullaby_id)
    if lullaby is None:
        raise not_found("자장가")
    return file_response(lullaby.audio_path, "audio/wav")


@router.delete("/lullabies/{lullaby_id}", status_code=204)
async def delete_lullaby(
    request: Request,
    lullaby_id: str,
    session: AsyncSession = Depends(session_dependency),
) -> None:
    lullaby = await session.get(Lullaby, lullaby_id)
    if lullaby is None:
        raise not_found("자장가")
    path = lullaby.audio_path
    await session.delete(lullaby)
    await session.commit()
    request.app.state.media_store.delete(path)


@router.get("/library", response_model=list[LibraryItem])
async def list_library(session: AsyncSession = Depends(session_dependency)) -> list[LibraryItem]:
    books = (
        (
            await session.scalars(
                select(Book)
                .options(selectinload(Book.pages).selectinload(BookPage.recording))
                .order_by(Book.updated_at.desc())
            )
        )
        .unique()
        .all()
    )
    lullabies = (await session.scalars(select(Lullaby).order_by(Lullaby.updated_at.desc()))).all()
    items = []
    for book in books:
        recordings = [page.recording for page in book.pages if page.recording]
        if (
            recordings
            and len(recordings) == len(book.pages)
            and all(recording.status == JobStatus.SUCCEEDED.value for recording in recordings)
        ):
            book_status = "ready"
        elif any(
            recording.status in {JobStatus.QUEUED.value, JobStatus.RUNNING.value}
            for recording in recordings
        ):
            book_status = "processing"
        elif recordings:
            book_status = "partial"
        else:
            book_status = "draft"
        items.append(
            LibraryItem(
                id=book.id,
                kind="book",
                title=book.title,
                status=book_status,
                playable_url=f"/v1/books/{book.id}/playback-manifest",
                updated_at=book.updated_at,
            )
        )
    items.extend(
        LibraryItem(
            id=item.id,
            kind="lullaby",
            title=item.title,
            status=item.status,
            playable_url=f"/v1/lullabies/{item.id}/audio" if item.audio_path else None,
            updated_at=item.updated_at,
        )
        for item in lullabies
    )
    return sorted(items, key=lambda item: item.updated_at, reverse=True)


@router.get("/jobs/{job_id}", response_model=JobRead)
async def get_job(job_id: str, session: AsyncSession = Depends(session_dependency)) -> JobRead:
    job = await session.get(Job, job_id)
    if job is None:
        raise not_found("작업")
    return JobRead.model_validate(job)
