from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi import (
    Path as ApiPath,
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
    SingingLullaby,
    VoiceProfile,
    VoiceSample,
)
from app.openapi import (
    AUDIO_FILE_RESPONSE,
    COMMON_ERROR_RESPONSES,
    FILE_TOO_LARGE_RESPONSE,
    IMAGE_FILE_RESPONSE,
    INSUFFICIENT_SAMPLES_RESPONSE,
    NOT_FOUND_RESPONSE,
    PROFILE_IN_USE_RESPONSE,
    PROFILE_NOT_READY_RESPONSE,
    QUEUE_FULL_RESPONSE,
    SAMPLE_LIMIT_RESPONSE,
    SEEDVC_UNAVAILABLE_RESPONSE,
    TAG_BOOKS,
    TAG_JOBS,
    TAG_LIBRARY,
    TAG_LULLABIES,
    TAG_PROFILES,
    TAG_SINGING_LULLABIES,
    UNSUPPORTED_AUDIO_RESPONSE,
)
from app.schemas import (
    BookCreate,
    BookPageRead,
    BookRead,
    JobAccepted,
    JobRead,
    LibraryItem,
    LullabyCreate,
    LullabyPlaybackPlan,
    LullabyPlaybackPlanRequest,
    LullabyRead,
    PlaybackManifest,
    PlaybackPage,
    PreviewRequest,
    RecordingRead,
    SingingLullabyCreate,
    SingingLullabyPlaybackPlan,
    SingingLullabyRead,
    SingingSourceRead,
    VoiceProfileCreate,
    VoiceProfileRead,
    VoiceSampleRead,
)
from app.security import require_api_key
from app.singing import SingingCatalog, SingingSource

ProfileId = Annotated[str, ApiPath(description="목소리 프로필 UUID")]
SampleId = Annotated[str, ApiPath(description="음성 샘플 UUID")]
BookId = Annotated[str, ApiPath(description="동화책 UUID")]
PageNumber = Annotated[int, ApiPath(ge=1, description="1부터 시작하는 페이지 번호")]
LullabyId = Annotated[str, ApiPath(description="자장가 UUID")]
SingingSourceId = Annotated[
    str,
    ApiPath(pattern=r"^[a-z0-9-]+$", description="한국어 무반주 자장가 소스 ID"),
]
SingingLullabyId = Annotated[str, ApiPath(description="Seed-VC 가창 자장가 변환 UUID")]
JobId = Annotated[str, ApiPath(description="비동기 작업 UUID")]
AudioSource = Annotated[
    Literal["original", "clarified"],
    Query(description="재생할 음성 소스. original은 정규화 원본, clarified는 재합성 음성"),
]

router = APIRouter(
    prefix="/v1",
    dependencies=[Depends(require_api_key)],
    responses=COMMON_ERROR_RESPONSES,
)


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


def singing_source_read(source: SingingSource) -> SingingSourceRead:
    return SingingSourceRead(
        id=source.id,
        title=source.title,
        description=source.description,
        lyrics=source.lyrics,
        region=source.region,
        duration_ms=source.duration_ms,
        audio_url=f"/v1/singing-lullabies/catalog/{source.id}/audio",
        composition_license=source.composition_license,
        recording_license=source.recording_license,
        attribution=source.attribution,
    )


def singing_lullaby_read(item: SingingLullaby, source: SingingSource) -> SingingLullabyRead:
    return SingingLullabyRead(
        id=item.id,
        source_id=item.source_id,
        profile_id=item.profile_id,
        title=source.title,
        lyrics=source.lyrics,
        status=item.status,
        repeat_count=item.repeat_count,
        timer_minutes=item.timer_minutes,
        diffusion_steps=item.diffusion_steps,
        semitone_shift=item.semitone_shift,
        audio_url=(
            f"/v1/singing-lullabies/conversions/{item.id}/audio" if item.audio_path else None
        ),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def require_singing_source(catalog: SingingCatalog, source_id: str) -> SingingSource:
    source = catalog.get(source_id)
    if source is None:
        # DB 레코드와 배포된 불변 카탈로그가 어긋나면 잘못된 성공 응답을 만들지 않는다.
        raise HTTPException(
            status_code=500,
            detail={
                "code": "singing_catalog_inconsistent",
                "message": "가창 자장가 카탈로그와 저장 데이터가 일치하지 않습니다",
            },
        )
    return source


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


def file_response(path_value: str | Path | None, media_type: str) -> FileResponse:
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


@router.post(
    "/voice-profiles",
    response_model=VoiceProfileRead,
    status_code=201,
    tags=[TAG_PROFILES],
    summary="목소리 프로필 생성",
    description=(
        "음성 출처와 소유자 동의를 기록한 초안 프로필을 생성합니다. "
        "생성 후 음성 샘플 5~20개를 등록하고 미리듣기를 생성해야 사용할 수 있습니다."
    ),
    response_description="생성된 초안 목소리 프로필",
)
async def create_voice_profile(
    payload: VoiceProfileCreate,
    session: AsyncSession = Depends(session_dependency),
) -> VoiceProfileRead:
    profile = VoiceProfile(**payload.model_dump())
    session.add(profile)
    await session.commit()
    await session.refresh(profile, attribute_names=["samples"])
    return profile_read(profile)


@router.get(
    "/voice-profiles",
    response_model=list[VoiceProfileRead],
    tags=[TAG_PROFILES],
    summary="목소리 프로필 목록 조회",
    description="최근 생성 순으로 프로필 상태, 샘플 수와 미리듣기 URL을 조회합니다.",
    response_description="목소리 프로필 목록",
)
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


@router.get(
    "/voice-profiles/{profile_id}",
    response_model=VoiceProfileRead,
    tags=[TAG_PROFILES],
    summary="목소리 프로필 상세 조회",
    description="프로필의 준비 상태, 샘플 수와 현재 미리듣기 버전을 조회합니다.",
    response_description="목소리 프로필 상세",
    responses={404: NOT_FOUND_RESPONSE},
)
async def get_voice_profile(
    profile_id: ProfileId, session: AsyncSession = Depends(session_dependency)
) -> VoiceProfileRead:
    return profile_read(await get_profile_with_samples(session, profile_id))


@router.post(
    "/voice-profiles/{profile_id}/samples",
    response_model=VoiceSampleRead,
    status_code=201,
    tags=[TAG_PROFILES],
    summary="목소리 학습 샘플 등록",
    description=(
        "샘플 문장과 해당 문장을 읽은 오디오를 multipart/form-data로 등록합니다. "
        "WAV·FLAC·OGG·MP3·M4A·WebM을 받아 16kHz mono WAV로 정규화합니다. "
        "샘플을 변경하면 기존 미리듣기는 무효화됩니다."
    ),
    response_description="정규화 및 저장된 음성 샘플 메타데이터",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: SAMPLE_LIMIT_RESPONSE,
        413: FILE_TOO_LARGE_RESPONSE,
        415: UNSUPPORTED_AUDIO_RESPONSE,
    },
)
async def add_voice_sample(
    request: Request,
    profile_id: ProfileId,
    prompt_text: str = Form(
        min_length=1,
        max_length=500,
        description="업로드한 음성에서 실제로 읽은 문장",
        examples=["오늘도 너와 함께해서 행복해."],
    ),
    audio: UploadFile = File(description="최대 25MB, 0.5~180초의 음성 파일"),
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
    request.app.state.media_store.delete(
        request.app.state.media_store.profile_reference_path(profile.id)
    )
    return VoiceSampleRead.model_validate(sample)


@router.get(
    "/voice-profiles/{profile_id}/samples",
    response_model=list[VoiceSampleRead],
    tags=[TAG_PROFILES],
    summary="목소리 학습 샘플 목록 조회",
    description="프로필에 등록된 샘플 문장과 음성 메타데이터를 조회합니다.",
    response_description="목소리 학습 샘플 목록",
    responses={404: NOT_FOUND_RESPONSE},
)
async def list_voice_samples(
    profile_id: ProfileId, session: AsyncSession = Depends(session_dependency)
) -> list[VoiceSampleRead]:
    profile = await get_profile_with_samples(session, profile_id)
    return [VoiceSampleRead.model_validate(sample) for sample in profile.samples]


@router.delete(
    "/voice-profiles/{profile_id}/samples/{sample_id}",
    status_code=204,
    tags=[TAG_PROFILES],
    summary="목소리 학습 샘플 삭제",
    description="선택한 샘플만 삭제하고 기존 미리듣기를 무효화합니다.",
    responses={404: NOT_FOUND_RESPONSE},
)
async def delete_voice_sample(
    request: Request,
    profile_id: ProfileId,
    sample_id: SampleId,
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
    request.app.state.media_store.delete(
        request.app.state.media_store.profile_reference_path(profile.id)
    )


@router.delete(
    "/voice-profiles/{profile_id}",
    status_code=204,
    tags=[TAG_PROFILES],
    summary="목소리 프로필 삭제",
    description=(
        "프로필과 모든 원본·정규화 샘플·미리듣기 파일을 삭제합니다. "
        "책 녹음이나 자장가에서 사용 중인 프로필은 먼저 연관 콘텐츠를 삭제해야 합니다."
    ),
    responses={404: NOT_FOUND_RESPONSE, 409: PROFILE_IN_USE_RESPONSE},
)
async def delete_voice_profile(
    request: Request,
    profile_id: ProfileId,
    session: AsyncSession = Depends(session_dependency),
) -> None:
    profile = await get_profile_with_samples(session, profile_id)
    recording_count = await session.scalar(
        select(func.count(PageRecording.id)).where(PageRecording.profile_id == profile_id)
    )
    lullaby_count = await session.scalar(
        select(func.count(Lullaby.id)).where(Lullaby.profile_id == profile_id)
    )
    singing_lullaby_count = await session.scalar(
        select(func.count(SingingLullaby.id)).where(SingingLullaby.profile_id == profile_id)
    )
    if recording_count or lullaby_count or singing_lullaby_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "profile_in_use",
                "message": "이 프로필을 사용한 책 녹음과 자장가를 먼저 삭제해야 합니다",
            },
        )
    paths: list[str | Path | None] = [
        profile.preview_path,
        request.app.state.media_store.profile_reference_path(profile.id),
    ]
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
    tags=[TAG_PROFILES],
    summary="목소리 프로필 미리듣기 생성·재생성",
    description=(
        "등록된 5~20개 샘플로 VoxCPM2 참조 음성을 만들고 요청 문장을 비동기로 합성합니다. "
        "응답의 status_url을 폴링한 뒤 성공하면 preview_url을 재생합니다."
    ),
    response_description="접수된 미리듣기 생성 작업",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: INSUFFICIENT_SAMPLES_RESPONSE,
        503: QUEUE_FULL_RESPONSE,
    },
)
async def generate_profile_preview(
    request: Request,
    profile_id: ProfileId,
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


@router.get(
    "/voice-profiles/{profile_id}/preview/audio",
    response_class=FileResponse,
    tags=[TAG_PROFILES],
    summary="목소리 프로필 미리듣기 재생",
    description="생성이 완료된 최신 미리듣기 WAV를 Range 요청 가능한 형태로 반환합니다.",
    responses=AUDIO_FILE_RESPONSE,
)
async def get_profile_preview_audio(
    profile_id: ProfileId, session: AsyncSession = Depends(session_dependency)
) -> FileResponse:
    profile = await session.get(VoiceProfile, profile_id)
    if profile is None:
        raise not_found("목소리 프로필")
    return file_response(profile.preview_path, "audio/wav")


@router.post(
    "/books",
    response_model=BookRead,
    status_code=201,
    tags=[TAG_BOOKS],
    summary="동화책 생성",
    description=(
        "제목·저자와 페이지별 원문을 한 번에 등록합니다. "
        "페이지 번호는 책 안에서 중복될 수 없습니다."
    ),
    response_description="페이지가 포함된 새 동화책",
)
async def create_book(
    payload: BookCreate, session: AsyncSession = Depends(session_dependency)
) -> BookRead:
    book = Book(title=payload.title, author=payload.author)
    book.pages = [BookPage(**page.model_dump()) for page in payload.pages]
    session.add(book)
    await session.commit()
    return book_read(await get_book_with_pages(session, book.id))


@router.get(
    "/books",
    response_model=list[BookRead],
    tags=[TAG_BOOKS],
    summary="동화책 목록 조회",
    description="최근 수정 순으로 페이지 텍스트·이미지 URL·녹음 처리 상태를 함께 조회합니다.",
    response_description="동화책 목록",
)
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


@router.get(
    "/books/{book_id}",
    response_model=BookRead,
    tags=[TAG_BOOKS],
    summary="동화책 상세 조회",
    description=(
        "프론트 페이지 뷰에 필요한 텍스트, 이미지와 녹음 결과를 페이지 순서대로 반환합니다."
    ),
    response_description="페이지가 포함된 동화책 상세",
    responses={404: NOT_FOUND_RESPONSE},
)
async def get_book(
    book_id: BookId, session: AsyncSession = Depends(session_dependency)
) -> BookRead:
    return book_read(await get_book_with_pages(session, book_id))


@router.delete(
    "/books/{book_id}",
    status_code=204,
    tags=[TAG_BOOKS],
    summary="동화책 삭제",
    description="동화책, 페이지, 페이지 이미지와 모든 원본·재합성 음성을 함께 삭제합니다.",
    responses={404: NOT_FOUND_RESPONSE},
)
async def delete_book(
    request: Request,
    book_id: BookId,
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


@router.put(
    "/books/{book_id}/pages/{page_number}/image",
    status_code=204,
    tags=[TAG_BOOKS],
    summary="동화책 페이지 이미지 등록·교체",
    description=(
        "선택한 페이지의 이미지만 multipart/form-data로 등록하거나 교체합니다. "
        "검증 후 메타데이터를 제거한 WebP로 저장합니다."
    ),
    responses={404: NOT_FOUND_RESPONSE, 413: FILE_TOO_LARGE_RESPONSE},
)
async def put_page_image(
    request: Request,
    book_id: BookId,
    page_number: PageNumber,
    image: UploadFile = File(description="최대 10MB, 4천만 픽셀 이하의 페이지 이미지"),
    session: AsyncSession = Depends(session_dependency),
) -> None:
    page = await get_page(session, book_id, page_number)
    new_path = await request.app.state.media_store.save_image(image)
    old_path = page.image_path
    page.image_path = str(new_path)
    await session.commit()
    request.app.state.media_store.delete(old_path)


@router.get(
    "/books/{book_id}/pages/{page_number}/image",
    response_class=FileResponse,
    tags=[TAG_BOOKS],
    summary="동화책 페이지 이미지 조회",
    description="저장 시 메타데이터가 제거된 WebP 이미지를 반환합니다.",
    responses=IMAGE_FILE_RESPONSE,
)
async def get_page_image(
    book_id: BookId,
    page_number: PageNumber,
    session: AsyncSession = Depends(session_dependency),
) -> FileResponse:
    page = await get_page(session, book_id, page_number)
    return file_response(page.image_path, "image/webp")


@router.put(
    "/books/{book_id}/pages/{page_number}/recording",
    response_model=JobAccepted,
    status_code=202,
    tags=[TAG_BOOKS],
    summary="페이지 음성 녹음·재녹음",
    description=(
        "선택한 페이지의 부모 음성을 등록합니다. 기존 녹음이 있으면 "
        "해당 페이지만 새 버전으로 교체하고 "
        "STT → LLM 문장 복원 → 감정 분류 → VoxCPM2 재합성을 비동기로 실행합니다. "
        "완료 여부는 응답의 status_url을 폴링합니다."
    ),
    response_description="접수된 페이지 음성 처리 작업",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: PROFILE_NOT_READY_RESPONSE,
        413: FILE_TOO_LARGE_RESPONSE,
        415: UNSUPPORTED_AUDIO_RESPONSE,
        503: QUEUE_FULL_RESPONSE,
    },
)
async def put_page_recording(
    request: Request,
    book_id: BookId,
    page_number: PageNumber,
    profile_id: str = Form(description="미리듣기 확인이 완료된 목소리 프로필 UUID"),
    audio: UploadFile = File(description="최대 25MB, 0.5~180초의 페이지 녹음"),
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


@router.get(
    "/books/{book_id}/pages/{page_number}/audio",
    response_class=FileResponse,
    tags=[TAG_BOOKS],
    summary="페이지 원본·재합성 음성 재생",
    description=(
        "source 쿼리로 정규화한 부모 원본과 또렷하게 재합성한 부모 음성을 전환해 재생합니다. "
        "브라우저 오디오 탐색을 위해 HTTP Range를 지원합니다."
    ),
    responses=AUDIO_FILE_RESPONSE,
)
async def get_page_audio(
    book_id: BookId,
    page_number: PageNumber,
    source: AudioSource = "clarified",
    session: AsyncSession = Depends(session_dependency),
) -> FileResponse:
    page = await get_page(session, book_id, page_number)
    if page.recording is None:
        raise not_found("페이지 녹음")
    path = page.recording.normalized_path if source == "original" else page.recording.clarified_path
    return file_response(path, "audio/wav")


@router.get(
    "/books/{book_id}/playback-manifest",
    response_model=PlaybackManifest,
    tags=[TAG_BOOKS],
    summary="동화책 재생 매니페스트 조회",
    description=(
        "수동 페이지 넘김 화면에서 필요한 이미지·원본·재합성 URL과 녹음 버전을 한 번에 반환합니다. "
        "프론트는 다음 페이지 오디오를 미리 로드해 전환 지연을 줄일 수 있습니다."
    ),
    response_description="페이지 순서대로 정렬된 재생 매니페스트",
    responses={404: NOT_FOUND_RESPONSE},
)
async def get_playback_manifest(
    book_id: BookId, session: AsyncSession = Depends(session_dependency)
) -> PlaybackManifest:
    book = await get_book_with_pages(session, book_id)
    pages = []
    for page in book.pages:
        recording = page.recording
        available_sources = []
        if recording:
            available_sources.append("original")
        if recording and recording.clarified_path:
            available_sources.append("clarified")
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
                available_sources=available_sources,
                version=recording.version if recording else None,
            )
        )
    return PlaybackManifest(book_id=book.id, title=book.title, pages=pages)


@router.post(
    "/lullabies",
    response_model=JobAccepted,
    status_code=202,
    tags=[TAG_LULLABIES],
    summary="부모 음색 자장가 생성",
    description=(
        "준비된 목소리 프로필로 가사를 낭독한 자장가 WAV를 비동기로 생성합니다. "
        "repeat_count와 timer_minutes는 프론트 재생 루틴에 전달되는 설정입니다."
    ),
    response_description="접수된 자장가 생성 작업",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: PROFILE_NOT_READY_RESPONSE,
        503: QUEUE_FULL_RESPONSE,
    },
)
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


@router.get(
    "/lullabies",
    response_model=list[LullabyRead],
    tags=[TAG_LULLABIES],
    summary="자장가 목록 조회",
    description="최근 수정 순으로 생성 상태, 반복·타이머 설정과 재생 URL을 조회합니다.",
    response_description="자장가 목록",
)
async def list_lullabies(
    session: AsyncSession = Depends(session_dependency),
) -> list[LullabyRead]:
    items = (await session.scalars(select(Lullaby).order_by(Lullaby.updated_at.desc()))).all()
    return [lullaby_read(item) for item in items]


@router.get(
    "/lullabies/{lullaby_id}",
    response_model=LullabyRead,
    tags=[TAG_LULLABIES],
    summary="자장가 상세 조회",
    description="자장가 생성 상태와 프론트 재생 루틴 설정을 조회합니다.",
    response_description="자장가 상세",
    responses={404: NOT_FOUND_RESPONSE},
)
async def get_lullaby(
    lullaby_id: LullabyId, session: AsyncSession = Depends(session_dependency)
) -> LullabyRead:
    lullaby = await session.get(Lullaby, lullaby_id)
    if lullaby is None:
        raise not_found("자장가")
    return lullaby_read(lullaby)


@router.get(
    "/lullabies/{lullaby_id}/audio",
    response_class=FileResponse,
    tags=[TAG_LULLABIES],
    summary="자장가 음성 재생",
    description="생성이 완료된 자장가 WAV를 Range 요청 가능한 형태로 반환합니다.",
    responses=AUDIO_FILE_RESPONSE,
)
async def get_lullaby_audio(
    lullaby_id: LullabyId, session: AsyncSession = Depends(session_dependency)
) -> FileResponse:
    lullaby = await session.get(Lullaby, lullaby_id)
    if lullaby is None:
        raise not_found("자장가")
    return file_response(lullaby.audio_path, "audio/wav")


@router.post(
    "/lullabies/{lullaby_id}/playback-plan",
    response_model=LullabyPlaybackPlan,
    tags=[TAG_LULLABIES],
    summary="자장가 자동재생 계획 생성",
    description=(
        "저장된 반복·타이머 설정 또는 이번 요청의 재정의 값을 프론트 자동재생 명령으로 반환합니다. "
        "프론트는 audio_url을 연속 재생하고 repeat_count 충족 또는 "
        "timer_seconds 만료 시 중단합니다."
    ),
    response_description="프론트 자동재생에 바로 사용할 수 있는 실행 계획",
    responses={404: NOT_FOUND_RESPONSE, 409: PROFILE_NOT_READY_RESPONSE},
)
async def create_lullaby_playback_plan(
    lullaby_id: LullabyId,
    payload: LullabyPlaybackPlanRequest,
    session: AsyncSession = Depends(session_dependency),
) -> LullabyPlaybackPlan:
    lullaby = await session.get(Lullaby, lullaby_id)
    if lullaby is None:
        raise not_found("자장가")
    if lullaby.status != JobStatus.SUCCEEDED.value or not lullaby.audio_path:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "lullaby_not_ready",
                "message": "생성이 완료된 자장가만 재생할 수 있습니다",
            },
        )
    repeat_count = payload.repeat_count or lullaby.repeat_count
    timer_minutes = payload.timer_minutes or lullaby.timer_minutes
    return LullabyPlaybackPlan(
        lullaby_id=lullaby.id,
        audio_url=f"/v1/lullabies/{lullaby.id}/audio",
        repeat_count=repeat_count,
        loop=repeat_count > 1,
        timer_seconds=timer_minutes * 60 if timer_minutes else None,
        stop_on_timer=timer_minutes is not None,
    )


@router.delete(
    "/lullabies/{lullaby_id}",
    status_code=204,
    tags=[TAG_LULLABIES],
    summary="자장가 삭제",
    description="자장가 메타데이터와 생성된 음성 파일을 함께 삭제합니다.",
    responses={404: NOT_FOUND_RESPONSE},
)
async def delete_lullaby(
    request: Request,
    lullaby_id: LullabyId,
    session: AsyncSession = Depends(session_dependency),
) -> None:
    lullaby = await session.get(Lullaby, lullaby_id)
    if lullaby is None:
        raise not_found("자장가")
    path = lullaby.audio_path
    await session.delete(lullaby)
    await session.commit()
    request.app.state.media_store.delete(path)


@router.get(
    "/singing-lullabies/catalog",
    response_model=list[SingingSourceRead],
    tags=[TAG_SINGING_LULLABIES],
    summary="한국어 무반주 자장가 카탈로그 조회",
    description=(
        "Seed-VC 변환용으로 수집·생성한 한국 전래 무반주 가이드 보컬의 제목, 가사, "
        "길이, 라이선스와 원본 재생 URL을 반환합니다."
    ),
    response_description="선택 가능한 한국어 무반주 자장가 목록",
)
async def list_singing_sources(request: Request) -> list[SingingSourceRead]:
    return [singing_source_read(item) for item in request.app.state.singing_catalog.list()]


@router.get(
    "/singing-lullabies/catalog/{source_id}/audio",
    response_class=FileResponse,
    tags=[TAG_SINGING_LULLABIES],
    summary="무반주 자장가 원본 미리듣기",
    description="목소리 변환 전 한국어 가이드 보컬 WAV를 Range 요청 가능한 형태로 반환합니다.",
    responses=AUDIO_FILE_RESPONSE,
)
async def get_singing_source_audio(request: Request, source_id: SingingSourceId) -> FileResponse:
    source = request.app.state.singing_catalog.get(source_id)
    if source is None:
        raise not_found("무반주 자장가 소스")
    return file_response(source.audio_path, "audio/wav")


@router.post(
    "/singing-lullabies/conversions",
    response_model=JobAccepted,
    status_code=202,
    tags=[TAG_SINGING_LULLABIES],
    summary="Seed-VC 부모 음색 자장가 변환",
    description=(
        "카탈로그의 한국어 무반주 자장가를 선택해 음높이·리듬을 유지하면서 ready 상태인 "
        "부모 목소리 프로필로 비동기 변환합니다. 기존 VoxCPM2 자장가 낭독 API와 별도입니다."
    ),
    response_description="접수된 Seed-VC 가창 음색 변환 작업",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: PROFILE_NOT_READY_RESPONSE,
        503: SEEDVC_UNAVAILABLE_RESPONSE,
    },
)
async def create_singing_lullaby(
    request: Request,
    payload: SingingLullabyCreate,
    session: AsyncSession = Depends(session_dependency),
) -> JobAccepted:
    source = request.app.state.singing_catalog.get(payload.source_id)
    if source is None:
        raise not_found("무반주 자장가 소스")
    profile = await get_profile_with_samples(session, payload.profile_id)
    if profile.status != ProfileStatus.READY.value:
        raise HTTPException(
            status_code=409,
            detail={"code": "profile_not_ready", "message": "준비된 목소리 프로필이 필요합니다"},
        )
    settings = request.app.state.settings
    if settings.inference_backend == "real" and not settings.seedvc_runtime_ready:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "seedvc_runtime_unavailable",
                "message": "Seed-VC CPU 런타임을 먼저 설치해야 합니다",
            },
        )
    item_data = payload.model_dump()
    item_data["diffusion_steps"] = payload.diffusion_steps or settings.seedvc_diffusion_steps
    item = SingingLullaby(**item_data)
    session.add(item)
    await session.flush()
    job = Job(kind="seedvc_lullaby_conversion", target_id=item.id)
    session.add(job)
    await session.commit()
    await enqueue_or_fail(request, session, job)
    return job_accepted(job)


@router.get(
    "/singing-lullabies/conversions",
    response_model=list[SingingLullabyRead],
    tags=[TAG_SINGING_LULLABIES],
    summary="Seed-VC 가창 자장가 목록 조회",
    description="최근 변환 순으로 선택 원곡, 부모 프로필, 생성 상태와 재생 설정을 조회합니다.",
    response_description="Seed-VC 가창 자장가 변환 목록",
)
async def list_singing_lullabies(
    request: Request,
    session: AsyncSession = Depends(session_dependency),
) -> list[SingingLullabyRead]:
    items = (
        await session.scalars(select(SingingLullaby).order_by(SingingLullaby.updated_at.desc()))
    ).all()
    catalog = request.app.state.singing_catalog
    return [
        singing_lullaby_read(item, require_singing_source(catalog, item.source_id))
        for item in items
    ]


@router.get(
    "/singing-lullabies/conversions/{conversion_id}",
    response_model=SingingLullabyRead,
    tags=[TAG_SINGING_LULLABIES],
    summary="Seed-VC 가창 자장가 상세 조회",
    description="단일 변환의 원곡·프로필·파라미터·상태와 결과 재생 URL을 조회합니다.",
    response_description="Seed-VC 가창 자장가 상세",
    responses={404: NOT_FOUND_RESPONSE},
)
async def get_singing_lullaby(
    request: Request,
    conversion_id: SingingLullabyId,
    session: AsyncSession = Depends(session_dependency),
) -> SingingLullabyRead:
    item = await session.get(SingingLullaby, conversion_id)
    if item is None:
        raise not_found("가창 자장가")
    source = require_singing_source(request.app.state.singing_catalog, item.source_id)
    return singing_lullaby_read(item, source)


@router.get(
    "/singing-lullabies/conversions/{conversion_id}/audio",
    response_class=FileResponse,
    tags=[TAG_SINGING_LULLABIES],
    summary="Seed-VC 변환 자장가 재생",
    description="멜로디를 유지하고 부모 음색으로 변환한 WAV를 Range 요청 가능하게 반환합니다.",
    responses=AUDIO_FILE_RESPONSE,
)
async def get_singing_lullaby_audio(
    conversion_id: SingingLullabyId,
    session: AsyncSession = Depends(session_dependency),
) -> FileResponse:
    item = await session.get(SingingLullaby, conversion_id)
    if item is None:
        raise not_found("가창 자장가")
    return file_response(item.audio_path, "audio/wav")


@router.post(
    "/singing-lullabies/conversions/{conversion_id}/playback-plan",
    response_model=SingingLullabyPlaybackPlan,
    tags=[TAG_SINGING_LULLABIES],
    summary="Seed-VC 자장가 자동재생 계획 생성",
    description="저장된 설정 또는 이번 요청 값을 반복·타이머 자동재생 계약으로 반환합니다.",
    response_description="프론트 자동재생 실행 계획",
    responses={404: NOT_FOUND_RESPONSE, 409: PROFILE_NOT_READY_RESPONSE},
)
async def create_singing_lullaby_playback_plan(
    conversion_id: SingingLullabyId,
    payload: LullabyPlaybackPlanRequest,
    session: AsyncSession = Depends(session_dependency),
) -> SingingLullabyPlaybackPlan:
    item = await session.get(SingingLullaby, conversion_id)
    if item is None:
        raise not_found("가창 자장가")
    if item.status != JobStatus.SUCCEEDED.value or not item.audio_path:
        raise HTTPException(
            status_code=409,
            detail={"code": "lullaby_not_ready", "message": "변환 완료 후 재생할 수 있습니다"},
        )
    repeat_count = payload.repeat_count or item.repeat_count
    timer_minutes = payload.timer_minutes or item.timer_minutes
    return SingingLullabyPlaybackPlan(
        conversion_id=item.id,
        audio_url=f"/v1/singing-lullabies/conversions/{item.id}/audio",
        repeat_count=repeat_count,
        loop=repeat_count > 1,
        timer_seconds=timer_minutes * 60 if timer_minutes else None,
        stop_on_timer=timer_minutes is not None,
    )


@router.delete(
    "/singing-lullabies/conversions/{conversion_id}",
    status_code=204,
    tags=[TAG_SINGING_LULLABIES],
    summary="Seed-VC 가창 자장가 삭제",
    description="변환 메타데이터와 생성 WAV를 삭제하며 카탈로그 원본은 유지합니다.",
    responses={404: NOT_FOUND_RESPONSE},
)
async def delete_singing_lullaby(
    request: Request,
    conversion_id: SingingLullabyId,
    session: AsyncSession = Depends(session_dependency),
) -> None:
    item = await session.get(SingingLullaby, conversion_id)
    if item is None:
        raise not_found("가창 자장가")
    path = item.audio_path
    await session.delete(item)
    await session.commit()
    request.app.state.media_store.delete(path)


@router.get(
    "/library",
    response_model=list[LibraryItem],
    tags=[TAG_LIBRARY],
    summary="콘텐츠 라이브러리 통합 조회",
    description=(
        "동화책과 자장가를 최근 수정 순으로 통합 조회합니다. "
        "playable_url이 null이면 아직 재생할 수 없습니다."
    ),
    response_description="책·자장가 통합 콘텐츠 목록",
)
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
                delete_url=f"/v1/books/{book.id}",
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
            delete_url=f"/v1/lullabies/{item.id}",
            updated_at=item.updated_at,
        )
        for item in lullabies
    )
    return sorted(items, key=lambda item: item.updated_at, reverse=True)


@router.get(
    "/jobs/{job_id}",
    response_model=JobRead,
    tags=[TAG_JOBS],
    summary="비동기 작업 상태 조회",
    description=(
        "202 응답에서 받은 작업을 조회합니다. queued·running 동안 1~2초 간격으로 재조회하고, "
        "succeeded 또는 failed에서 폴링을 종료합니다. failed이면 "
        "error_code와 error_message를 표시합니다."
    ),
    response_description="비동기 작업의 현재 상태와 오류 정보",
    responses={404: NOT_FOUND_RESPONSE},
)
async def get_job(job_id: JobId, session: AsyncSession = Depends(session_dependency)) -> JobRead:
    job = await session.get(Job, job_id)
    if job is None:
        raise not_found("작업")
    return JobRead.model_validate(job)
