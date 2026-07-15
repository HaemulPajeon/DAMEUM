# 담음 API

구음장애가 있는 부모의 발화를 텍스트로 복원하고, 감정을 반영한 또렷한 부모 음색으로 재합성하는 로컬 FastAPI REST API입니다. 프론트엔드는 책 페이지, 원본/재합성 오디오, 목소리 프로필, 자장가와 비동기 추론 작업을 HTTP API로 연동할 수 있습니다.

## 실행 환경

- Python 3.11 또는 3.12
- RAM 16GB 이상
- CPU 전용, API와 프론트엔드를 같은 PC에서 실행
- Windows 10/11 또는 macOS
- 외부 배포 없이 `127.0.0.1` 바인딩

모델은 다음 구성을 기본값으로 사용합니다.

| 단계 | 모델/런타임 | 선정 이유 |
|---|---|---|
| STT | Whisper small + 담음 구음장애 LoRA, CPU FP32 | AI-Hub 한국어 구음장애 음성에 미세조정한 프로젝트 모델 |
| 문장 복원 | Qwen3-1.7B GGUF Q8_0 + llama.cpp | 공식 양자화 모델, Windows/macOS CPU 지원 |
| 감정 분류 | KoELECTRA 한국어 6감정 분류 모델 | 한국어 문장 대상 소형 오픈소스 분류기 |
| 음성 합성 | VoxCPM2 2B | VoxCPM 계열 중 한국어·음성 복제·감정 스타일을 함께 지원하는 버전 |

VoxCPM2는 약 8GB의 모델 메모리가 필요하고 CPU 추론은 느립니다. 서버는 STT → 문장 복원 → 감정 분류 → TTS를 단일 큐에서 순차 처리하고, 기본적으로 작업이 끝날 때 모델을 해제해 16GB 환경의 메모리 경합을 줄입니다. API는 생성 요청에 `202 Accepted`를 반환하므로 프론트엔드는 작업 상태를 폴링해야 합니다.

### 로컬 실측

macOS ARM64, CPU 4스레드 조건에서 실제 모델 전체 흐름을 검증했습니다. 테스트 장비는 24GB RAM이며, 16GB 목표 환경과 같은 CPU·context·모델 해제 설정을 사용했습니다.

| 항목 | 결과 |
|---|---|
| Whisper small + 구음장애 LoRA CPU FP32 | 6.6초 한국어 WAV 전사 약 16~21초, 최대 RSS 약 1.95GB |
| Qwen3-1.7B Q8_0 | 손상 문장 복원 약 4~5초, idle sleep 시 RSS 약 120MB |
| KoELECTRA 감정 분류 | 이후 추론 약 0.02초, 최대 RSS 약 1.26GB |
| VoxCPM2 CPU | 48kHz mono WAV 생성 성공, 최대 RSS 약 8.41GB |
| HTTP 전체 페이지 작업 | STT → 교정 → 감정 → 합성 70.2초, 원문 완전 일치 |

Qwen은 활성 상태에서 약 4GB를 사용하지만 `--sleep-idle-seconds 2` 적용 후 메모리를 해제합니다. 전체 작업이 끝난 뒤 FastAPI worker는 약 892MB로 내려왔습니다. CPU 세대와 메모리 대역폭에 따라 시간은 달라집니다.

STT 어댑터는 `feat/dameum-stt-lora`의 학습 산출물을 `artifacts/stt/`에 포함한 것입니다. held-out
125개 음성에서 CER 64.3%에서 53.6%로 개선됐지만, 약 24분 분량으로 학습한 시연용 모델이므로
의료·안전 관련 문장의 정확성을 보장하지 않습니다. 서버는 시작 후 첫 실제 STT 요청에서
`openai/whisper-small` base 모델을 내려받아 로컬 캐시에 저장하며, 이후에는 네트워크 없이 실행합니다.
체크인된 어댑터는 로드 전 SHA-256을 검증합니다.

> 현재 자장가 기능은 부모 음색으로 가사를 부드럽게 **낭독**합니다. VoxCPM2는 노래 생성 모델이 아니므로 멜로디를 가진 가창은 별도 singing voice synthesis 모델이 필요합니다.

## 설치

### 공통

[`uv`](https://docs.astral.sh/uv/)를 설치한 뒤 저장소 루트의 `dameum-fastapi`로 이동해 실행합니다.

```bash
cd dameum-fastapi
uv sync --python 3.11 --extra ml --extra dev
```

macOS/Linux:

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
py -3.11 -c "import secrets; print(secrets.token_urlsafe(48))"
```

출력된 값을 `.env`의 `DAMEUM_API_KEY`에 넣습니다. 이 키는 프론트엔드의 `X-API-Key` 헤더와 같아야 합니다.

### llama.cpp 문장 복원 서버

Qwen 공식 GGUF를 CPU로 실행합니다. Windows는 `winget install llama.cpp`, macOS는 `brew install llama.cpp`로 설치할 수 있습니다.

```bash
llama-server \
  -hf Qwen/Qwen3-1.7B-GGUF:Q8_0 \
  --host 127.0.0.1 \
  --port 8081 \
  --api-key local-only \
  -ngl 0 \
  --sleep-idle-seconds 2
```

`--sleep-idle-seconds 2`는 문장 복원이 끝난 뒤 Qwen 모델 메모리를 해제합니다. VoxCPM2와 Qwen이 동시에 상주하지 않게 하므로 16GB 환경에서는 이 옵션을 제거하지 마세요.

PowerShell에서는 줄바꿈 문자로 백틱(`` ` ``)을 사용하거나 한 줄로 실행합니다.

### FastAPI 서버

```bash
uv run uvicorn app.main:create_app --factory \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 1
```

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- 상태 확인: `http://127.0.0.1:8000/health/ready`
- 모델 없이 API만 확인: `.env`에서 `DAMEUM_INFERENCE_BACKEND=mock`

`--reload`는 개발 중 코드 수정에만 사용합니다. 추론 작업 중 프로세스가 재시작되면 실행 중인 작업은 실패 처리됩니다.

## 프론트엔드 연동

모든 `/v1` 요청에 API 키를 전달합니다. 상태 확인 API는 인증 없이 접근할 수 있습니다.

```ts
const api = async (path: string, init: RequestInit = {}) =>
  fetch(`http://127.0.0.1:8000${path}`, {
    ...init,
    headers: {
      "X-API-Key": import.meta.env.VITE_DAMEUM_API_KEY,
      ...init.headers,
    },
  });
```

생성 API의 응답 예시는 다음과 같습니다.

```json
{
  "job_id": "c40c3cf0-6a96-4bcc-bc77-91de1ee28f9b",
  "status": "queued",
  "status_url": "/v1/jobs/c40c3cf0-6a96-4bcc-bc77-91de1ee28f9b"
}
```

`status_url`을 1~2초 간격으로 조회하고 `succeeded` 또는 `failed`에서 폴링을 종료합니다. 재생 화면에서는 `GET /v1/books/{book_id}/playback-manifest`를 먼저 가져와 현재 페이지와 다음 페이지의 이미지·오디오를 미리 로드합니다. 미디어 API는 HTTP Range와 ETag를 지원하므로 원본/재합성 토글과 페이지 전환 시 브라우저 캐시를 활용할 수 있습니다.

HTML `<audio src>`는 `X-API-Key` 헤더를 직접 보낼 수 없습니다. 미디어는 `fetch`로 인증 헤더를 붙여 받은 뒤 `Blob` URL로 재생하고, 사용이 끝난 URL은 `URL.revokeObjectURL()`로 해제하세요.

## 기능별 API 엔드포인트

모든 `/v1` API는 `X-API-Key`가 필요합니다. `{profile_id}`, `{book_id}`, `{lullaby_id}`, `{job_id}`는 UUID 문자열이고 `{page_number}`는 1부터 시작합니다.

### 목소리 프로필

| Method | Endpoint | operationId | 기능 |
|---|---|---|---|
| `GET` | `/v1/voice-profiles` | `list_voice_profiles` | 프로필 목록 조회 |
| `POST` | `/v1/voice-profiles` | `create_voice_profile` | 음성 출처와 동의를 포함한 프로필 생성 |
| `GET` | `/v1/voice-profiles/{profile_id}` | `get_voice_profile` | 상태·샘플 수·미리듣기 URL 조회 |
| `DELETE` | `/v1/voice-profiles/{profile_id}` | `delete_voice_profile` | 프로필과 음성 파일 삭제 |
| `POST` | `/v1/voice-profiles/{profile_id}/samples` | `add_voice_sample` | 발병 전·가족 기증·현재 음성 샘플 등록 |
| `GET` | `/v1/voice-profiles/{profile_id}/samples` | `list_voice_samples` | 등록 샘플 목록 조회 |
| `DELETE` | `/v1/voice-profiles/{profile_id}/samples/{sample_id}` | `delete_voice_sample` | 선택 샘플 삭제 |
| `POST` | `/v1/voice-profiles/{profile_id}/preview` | `generate_profile_preview` | 5~20개 샘플 기반 미리듣기 생성·재생성 |
| `GET` | `/v1/voice-profiles/{profile_id}/preview/audio` | `get_profile_preview_audio` | 미리듣기 WAV 재생 |

### 동화책과 페이지별 녹음

| Method | Endpoint | operationId | 기능 |
|---|---|---|---|
| `GET` | `/v1/books` | `list_books` | 페이지를 포함한 책 목록 조회 |
| `POST` | `/v1/books` | `create_book` | 페이지 원문으로 책 생성 |
| `GET` | `/v1/books/{book_id}` | `get_book` | 페이지 텍스트·이미지·녹음 결과 조회 |
| `DELETE` | `/v1/books/{book_id}` | `delete_book` | 책과 관련 미디어 삭제 |
| `PUT` | `/v1/books/{book_id}/pages/{page_number}/image` | `put_page_image` | 선택 페이지 이미지 등록·교체 |
| `GET` | `/v1/books/{book_id}/pages/{page_number}/image` | `get_page_image` | WebP 페이지 이미지 조회 |
| `PUT` | `/v1/books/{book_id}/pages/{page_number}/recording` | `put_page_recording` | 선택 페이지만 녹음·재녹음하고 AI 작업 접수 |
| `GET` | `/v1/books/{book_id}/pages/{page_number}/audio` | `get_page_audio` | `source=original|clarified` WAV 재생 |
| `GET` | `/v1/books/{book_id}/playback-manifest` | `get_playback_manifest` | 수동 넘김·토글·다음 페이지 프리패치 계약 조회 |

### 자장가와 콘텐츠 라이브러리

| Method | Endpoint | operationId | 기능 |
|---|---|---|---|
| `GET` | `/v1/lullabies` | `list_lullabies` | 자장가 목록 조회 |
| `POST` | `/v1/lullabies` | `create_lullaby` | 부모 음색 자장가 낭독 생성 작업 접수 |
| `GET` | `/v1/lullabies/{lullaby_id}` | `get_lullaby` | 자장가 상세·반복·타이머 설정 조회 |
| `DELETE` | `/v1/lullabies/{lullaby_id}` | `delete_lullaby` | 자장가와 WAV 삭제 |
| `GET` | `/v1/lullabies/{lullaby_id}/audio` | `get_lullaby_audio` | 생성된 자장가 WAV 재생 |
| `POST` | `/v1/lullabies/{lullaby_id}/playback-plan` | `create_lullaby_playback_plan` | 자동 반복·타이머 실행 계획 생성 |
| `GET` | `/v1/library` | `list_library` | 책·자장가 통합 목록과 재생·삭제 URL 조회 |

### 작업·상태

| Method | Endpoint | operationId | 기능 |
|---|---|---|---|
| `GET` | `/v1/jobs/{job_id}` | `get_job` | 비동기 AI 작업 진행률·결과 조회 |
| `GET` | `/health/live` | `live` | API 프로세스 생존 확인 |
| `GET` | `/health/ready` | `ready` | 큐와 모델 구성 확인 |

상세 엔드포인트, 오류 분기와 상태 전이는 [프론트엔드 연동 명세](docs/API.md)를 참고하세요.
서버를 실행하지 않고 타입·클라이언트를 생성할 때는 커밋된
[`docs/openapi.json`](docs/openapi.json)을 사용합니다.

```bash
# 백엔드 계약 변경 후 OpenAPI 스냅샷 갱신
uv run python -m scripts.export_openapi

# 프론트 저장소에서 TypeScript 타입 생성
npx openapi-typescript /path/to/DAMEUM/dameum-fastapi/docs/openapi.json \
  --output src/api/dameum-schema.d.ts
```

## 보안

- `127.0.0.1` 전용 실행과 로컬 CORS origin만 허용
- 32자 이상 API 키와 상수 시간 비교
- 허용 Host 제한 및 보안 응답 헤더
- 업로드 확장자를 신뢰하지 않고 파일 시그니처·크기·재생 시간 검증
- 음성은 16kHz mono WAV로 정규화하고 이미지는 메타데이터 제거 후 WebP 재인코딩
- 저장 파일명은 UUID로 생성하며 실제 경로는 API 응답에 노출하지 않음
- 가족 기증 음성을 포함한 모든 프로필에서 음성 소유자의 명시적 동의 필수
- 추론 큐 길이 제한과 단일 worker로 메모리 고갈 방지

로컬 시연이더라도 `.env`, `data/`, `models/`는 Git에 포함하지 않습니다. 실제 사용자 음성은 별도 동의 철회·보존 기간·완전 삭제 정책을 추가한 뒤 수집해야 합니다.

## 검증

```bash
uv run ruff check .
uv run python -m pytest -q
uv run python -m scripts.export_openapi
git diff --exit-code docs/openapi.json
```

테스트는 유효/비유효 파일 업로드, 동의 검증, 프로필 생성과 미리듣기, 페이지 재녹음 버전 교체, STT→LLM→감정→TTS 작업, 재생 manifest, 자장가와 콘텐츠 라이브러리를 포함합니다.

## 참고 자료

- [VoxCPM2 공식 설치 문서](https://voxcpm.readthedocs.io/en/latest/installation.html)
- [VoxCPM2 공식 사용 가이드](https://voxcpm.readthedocs.io/en/latest/usage_guide.html)
- [OpenAI Whisper small 공식 모델 카드](https://huggingface.co/openai/whisper-small)
- [PEFT 공식 저장소](https://github.com/huggingface/peft)
- [Qwen3-1.7B 공식 GGUF 모델 카드](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF)
- [FastAPI CORS 문서](https://fastapi.tiangolo.com/tutorial/cors/)
