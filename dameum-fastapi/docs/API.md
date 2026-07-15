# 담음 REST API 프론트엔드 연동 명세

이 문서는 프론트엔드 구현 규칙을 설명합니다. 필드 타입·필수 여부·제약·예제·응답 코드는
[`openapi.json`](openapi.json)이 단일 기준(Source of Truth)이며, 로컬 서버의
`http://127.0.0.1:8000/docs`에서 같은 계약을 Swagger UI로 확인하고 직접 호출할 수 있습니다.

## 1. 계약 기본 정보

| 항목 | 값 |
|---|---|
| OpenAPI | 3.1.0 |
| Base URL | `http://127.0.0.1:8000` |
| API 버전 prefix | `/v1` |
| 인증 | `X-API-Key` 헤더 |
| 요청 본문 | 기본 `application/json`, 파일 등록은 `multipart/form-data` |
| 오디오 응답 | `audio/wav`, HTTP Range 지원 |
| 이미지 응답 | `image/webp` |
| 시간 | UTC ISO 8601 문자열 |
| ID | UUID 문자열. 프론트에서 구조를 해석하지 않음 |

`/health/live`, `/health/ready`만 인증 없이 호출할 수 있습니다. API 키는 32자 이상이며 프론트
환경 변수와 FastAPI의 `DAMEUM_API_KEY`가 같아야 합니다. 쿼리 문자열·로컬 스토리지·로그에 키를
남기지 않습니다.

Swagger UI의 우측 **Authorize**에서 `X-API-Key`를 한 번 입력하면 `/v1` API를 실행할 수 있습니다.
브라우저를 새로 열면 키를 다시 입력하도록 인증 정보 영구 저장은 사용하지 않습니다.

## 2. 프론트 클라이언트 생성

백엔드 변경 후 `dameum-fastapi` 디렉터리에서 계약 파일을 갱신합니다.

```bash
uv run python -m scripts.export_openapi
```

프론트 저장소에서 스키마 타입만 생성할 때는 다음처럼 사용합니다.

```bash
npx openapi-typescript /path/to/DAMEUM/dameum-fastapi/docs/openapi.json \
  --output src/api/dameum-schema.d.ts
```

Fetch 클라이언트 전체를 생성하는 팀은 OpenAPI Generator의 안정(stable) `typescript-fetch`
generator를 사용할 수 있습니다.

```bash
npx @openapitools/openapi-generator-cli generate \
  -i /path/to/DAMEUM/dameum-fastapi/docs/openapi.json \
  -g typescript-fetch \
  -o src/api/generated \
  --additional-properties=supportsES6=true,useSingleRequestParameter=true
```

모든 작업은 함수명과 같은 고정 `operationId`를 가집니다. 경로 설명이나 태그가 바뀌어도 생성된
클라이언트 메서드명은 유지됩니다. `operationId`, 경로, HTTP method, 필수 필드, enum 값 또는 응답
타입 변경은 계약 변경으로 취급하고 프론트와 함께 검토합니다.

## 3. 공통 요청·오류 규격

JSON API 호출 예시입니다.

```ts
const response = await fetch(`http://127.0.0.1:8000${path}`, {
  ...init,
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": apiKey,
    ...init.headers,
  },
});
```

파일 업로드에서는 브라우저가 boundary를 만들도록 `Content-Type`을 직접 지정하지 않습니다.

```ts
const body = new FormData();
body.append("prompt_text", promptText);
body.append("audio", audioFile);

await fetch(`${baseUrl}/v1/voice-profiles/${profileId}/samples`, {
  method: "POST",
  headers: { "X-API-Key": apiKey },
  body,
});
```

JSON 오류는 같은 envelope을 사용합니다. 단, 잘못된 오디오 `Range` 요청에 대한 `416`은 브라우저
미디어 표준 동작에 맞춰 `text/plain`과 `Content-Range`를 반환합니다.

```json
{
  "detail": {
    "code": "profile_not_ready",
    "message": "미리듣기로 확인을 마친 목소리 프로필이 필요합니다",
    "errors": null
  }
}
```

검증 오류만 `errors`에 필드 경로와 사유가 포함됩니다.

```json
{
  "detail": {
    "code": "validation_error",
    "message": "요청 값이 올바르지 않습니다",
    "errors": [{ "field": "body.pages.0.text", "message": "Field required" }]
  }
}
```

| HTTP | 주요 `detail.code` | 프론트 처리 |
|---|---|---|
| `401` | `invalid_api_key` | 연동 설정 확인. 자동 무한 재시도 금지 |
| `404` | `not_found` | 목록을 갱신하고 상세 화면 종료 |
| `409` | `sample_limit` | 샘플 추가 비활성화 |
| `409` | `insufficient_samples` | 5~20개 샘플 등록 화면으로 이동 |
| `409` | `profile_not_ready` | 프로필 미리듣기 생성·확인 유도 |
| `409` | `profile_in_use` | 연관 책 녹음·자장가를 먼저 삭제하도록 안내 |
| `413` | `file_too_large` | 파일 재선택 안내 |
| `415` | `unsupported_audio` | 지원 형식 안내 |
| `422` | `validation_error`, `invalid_audio`, `invalid_audio_duration`, `invalid_image` | 필드 또는 파일 오류 표시 |
| `500` | `internal_error` | 일반 오류 표시 후 사용자가 재시도하도록 안내 |
| `503` | `queue_full` | `Retry-After` 초 뒤 제한적으로 재시도 |
| `503` | `seedvc_runtime_unavailable` | `scripts.setup_seedvc` 실행 후 상태 API 재확인 |

## 4. 브라우저 녹음 계약

마이크 권한 요청과 녹음 시작·정지는 프론트엔드에서 수행합니다. 백엔드는
`GET /v1/recording-capabilities`로 현재 업로드 제한, `MediaRecorder.isTypeSupported()` 검사 순서,
권장 `getUserMedia` 제약과 두 업로드 경로를 반환합니다. 값을 프론트에 중복 하드코딩하지 않습니다.

| operationId | Method / Path | 성공 | 업무 규칙 |
|---|---|---|---|
| `get_recording_capabilities` | `GET /v1/recording-capabilities` | `200` | MIME 우선순위·0.5~180초·25MB 제한·업로드 계약 |

- Chrome·Edge는 우선 `audio/webm;codecs=opus`를 사용합니다.
- Safari가 WebM/Opus를 지원하지 않으면 `audio/mp4;codecs=mp4a.40.2`를 사용합니다.
- `MediaRecorder.start(1000)`으로 1초마다 chunk를 받아 브라우저 메모리 급증을 막습니다.
- 정지 시 모든 `MediaStreamTrack`을 `stop()`해 마이크 표시와 장치 점유를 해제합니다.
- 녹음 중 페이지를 이탈하면 확인 UI를 표시하고, 업로드 완료 전 Blob을 폐기하지 않습니다.
- 프로필 샘플은 `prompt_text`, 동화 페이지는 ready 상태의 `profile_id`를 같이 보냅니다.
- `FormData` 전송 시 `Content-Type`을 직접 지정하지 않습니다.

브라우저가 보낸 MIME이나 확장자는 신뢰하지 않습니다. 서버는 WAV·FLAC·Ogg·MP3·MP4/M4A·WebM
시그니처를 확인하고 실제 디코딩에 성공한 입력만 16kHz mono PCM WAV로 저장합니다. 녹음 Blob은
`POST /v1/voice-profiles/{profile_id}/samples`와
`PUT /v1/books/{book_id}/pages/{page_number}/recording`에 그대로 사용할 수 있습니다.

## 5. 비동기 작업 계약

다음 API는 모델 추론을 기다리지 않고 `202 Accepted`를 반환합니다.

- `generate_profile_preview`: 목소리 프로필 미리듣기 생성·재생성
- `put_page_recording`: STT → 발화 의도 보존 LLM 교정 → 감정 분류 → VoxCPM2 재합성
- `create_lullaby`: 부모 음색 자장가 낭독 생성
- `create_singing_lullaby`: 원곡 멜로디를 유지한 Seed-VC 부모 음색 변환

```json
{
  "job_id": "c40c3cf0-6a96-4bcc-bc77-91de1ee28f9b",
  "status": "queued",
  "status_url": "/v1/jobs/c40c3cf0-6a96-4bcc-bc77-91de1ee28f9b"
}
```

프론트는 `status_url`을 즉시 한 번 조회한 뒤 1~2초 간격으로 폴링합니다. 화면 이탈·컴포넌트
unmount 때 요청을 취소하고, 같은 `job_id`에 폴러를 중복 생성하지 않습니다.

```text
queued -> running -> succeeded
                  -> failed
```

| 상태 | 의미 | UI 처리 |
|---|---|---|
| `queued` | 단일 CPU 추론 큐 대기 | 대기 상태와 취소 불가 안내 |
| `running` | 모델 파이프라인 실행 | `progress` 표시 |
| `succeeded` | 결과 저장 완료 | 폴링 종료 후 대상 상세 API 재조회 |
| `failed` | 처리 실패 | 폴링 종료 후 `error_message` 표시 |

`succeeded` 직후 결과 URL을 추측하지 말고 프로필·책·자장가 상세을 다시 조회합니다. 페이지 재녹음은
`version`이 증가하며 늦게 끝난 과거 작업이 최신 결과를 덮어쓰지 않습니다.

## 6. 목소리 프로필

권장 연동 순서는 다음과 같습니다.

1. `create_voice_profile`로 동의와 음성 출처를 저장합니다.
2. `add_voice_sample`을 5~20회 호출합니다.
3. `generate_profile_preview`를 호출하고 작업 성공까지 조회합니다.
4. 프로필을 다시 조회해 `status=ready`, `preview_url!=null`을 확인합니다.
5. 사용자가 미리듣기를 확인한 프로필만 페이지 녹음·자장가 생성에 사용합니다.

| operationId | Method / Path | 성공 | 업무 규칙 |
|---|---|---|---|
| `create_voice_profile` | `POST /v1/voice-profiles` | `201` | `consent_confirmed=true` 필수 |
| `list_voice_profiles` | `GET /v1/voice-profiles` | `200` | 최근 생성 순 |
| `get_voice_profile` | `GET /v1/voice-profiles/{profile_id}` | `200` | 상태·샘플 수·미리듣기 URL |
| `add_voice_sample` | `POST .../{profile_id}/samples` | `201` | `prompt_text`, `audio`; 추가 시 다시 `draft` |
| `list_voice_samples` | `GET .../{profile_id}/samples` | `200` | 샘플 문장과 길이 확인 |
| `delete_voice_sample` | `DELETE .../{profile_id}/samples/{sample_id}` | `204` | 선택 샘플만 제거, 미리듣기 무효화 |
| `generate_profile_preview` | `POST .../{profile_id}/preview` | `202` | 샘플 5~20개 필요 |
| `get_profile_preview_audio` | `GET .../{profile_id}/preview/audio` | `200` | `audio/wav` |
| `delete_voice_profile` | `DELETE /v1/voice-profiles/{profile_id}` | `204` | 사용 중이면 `409` |

`source_kind` enum은 `pre_illness`(발병 전), `family_donation`(가족 기증),
`current_voice`(현재 음성)입니다. 프로필 상태는 `draft`, `generating`, `ready`, `failed`입니다.

## 7. 동화책·페이지 녹음

| operationId | Method / Path | 성공 | 업무 규칙 |
|---|---|---|---|
| `create_book` | `POST /v1/books` | `201` | 페이지 원문 일괄 생성, 페이지 번호 중복 금지 |
| `list_books` | `GET /v1/books` | `200` | 최근 수정 순 |
| `get_book` | `GET /v1/books/{book_id}` | `200` | 이미지·녹음 처리 결과 포함 |
| `put_page_image` | `PUT .../pages/{page_number}/image` | `204` | 선택 페이지 이미지만 교체 |
| `get_page_image` | `GET .../pages/{page_number}/image` | `200` | `image/webp` |
| `put_page_recording` | `PUT .../pages/{page_number}/recording` | `202` | `profile_id`, `audio`; 선택 페이지만 새 버전 |
| `get_page_audio` | `GET .../pages/{page_number}/audio` | `200` | `source=original\|clarified` |
| `get_playback_manifest` | `GET /v1/books/{book_id}/playback-manifest` | `200` | 수동 재생·프리패치용 URL |
| `delete_book` | `DELETE /v1/books/{book_id}` | `204` | 책과 모든 관련 미디어 삭제 |

`recording`의 핵심 필드는 다음과 같습니다.

| 필드 | 의미 |
|---|---|
| `transcript` | 구음장애 음성 LoRA를 적용한 Whisper가 인식한 구음 원문 |
| `corrected_text` | LLM이 실제 발화 의도를 보존해 최소 교정한 최종 TTS 입력. 페이지 `text`와 다를 수 있음 |
| `emotion`, `emotion_score` | 한국어 감정 분류 label과 신뢰도 |
| `original_url` | 정규화된 부모 원본 음성 |
| `clarified_url` | 부모 음색을 유지해 또렷하게 재합성한 음성 |
| `version` | 같은 페이지의 재녹음 순서 |

수동 재생 화면은 `playback-manifest`를 먼저 받고 현재·다음 페이지 이미지와 오디오를 미리
`fetch`합니다. `available_sources`로 토글 가능 여부를 판단하고 `default_source=clarified`를 최초
선택값으로 사용합니다. `prefetch_next=true`와 `transition_budget_ms=300`은 300ms 이내 전환 목표를
위한 프론트 힌트이지, 서버가 300ms 내 추론을 끝낸다는 의미가 아닙니다.

## 8. 미디어 재생

HTML `<audio src>`와 `<img src>`는 `X-API-Key`를 직접 추가할 수 없으므로 인증 `fetch`로 Blob을
받아 Object URL로 연결합니다.

```ts
export async function loadProtectedMedia(path: string, apiKey: string) {
  const response = await fetch(`http://127.0.0.1:8000${path}`, {
    headers: { "X-API-Key": apiKey },
  });
  if (!response.ok) throw await response.json();
  return URL.createObjectURL(await response.blob());
}
```

사용이 끝난 URL은 `URL.revokeObjectURL()`로 해제합니다. 오디오 탐색이 필요한 플레이어는 `Range`
헤더를 사용하며 응답의 `Accept-Ranges`, `Content-Range`, `ETag`를 활용할 수 있습니다. 이때 CORS에
허용된 로컬 origin에서만 호출합니다.

## 9. 자장가·콘텐츠 라이브러리

| operationId | Method / Path | 성공 | 업무 규칙 |
|---|---|---|---|
| `create_lullaby` | `POST /v1/lullabies` | `202` | ready 프로필 필요 |
| `list_lullabies` | `GET /v1/lullabies` | `200` | 상태·재생 설정·URL |
| `get_lullaby` | `GET /v1/lullabies/{lullaby_id}` | `200` | 자장가 상세 |
| `get_lullaby_audio` | `GET /v1/lullabies/{lullaby_id}/audio` | `200` | `audio/wav` |
| `create_lullaby_playback_plan` | `POST /v1/lullabies/{lullaby_id}/playback-plan` | `200` | 자동 반복·타이머 실행 계획 |
| `delete_lullaby` | `DELETE /v1/lullabies/{lullaby_id}` | `204` | 메타데이터와 WAV 삭제 |
| `list_library` | `GET /v1/library` | `200` | 책·자장가 최근 수정 순 통합 목록 |

`playback-plan`은 저장된 `repeat_count`, `timer_minutes`를 초 단위 실행 계약으로 변환합니다. 요청
본문으로 이번 재생에만 반복 횟수와 타이머를 재정의할 수 있습니다. 현재 VoxCPM2 결과는 노래가
아니라 부모 음색의 부드러운 낭독입니다. `playable_url=null`이면 아직 재생 버튼을 활성화하지
않고, 라이브러리 삭제는 각 항목의 `delete_url`에 `DELETE`를 요청합니다.

## 10. Seed-VC 무반주 가창 자장가

기존 `/v1/lullabies`는 VoxCPM2 낭독이며 아래 API와 데이터 모델을 공유하지 않습니다. 프론트는
먼저 카탈로그에서 원곡을 재생하고 `source_id`와 ready 프로필을 선택해 변환을 요청합니다.

| operationId | Method / Path | 성공 | 업무 규칙 |
|---|---|---|---|
| `list_singing_sources` | `GET /v1/singing-lullabies/catalog` | `200` | 무반주 가창 프리셋·가사·라이선스 |
| `get_singing_source_audio` | `GET .../catalog/{source_id}/audio` | `200` | 변환 전 WAV 미리듣기 |
| `create_singing_lullaby` | `POST .../conversions` | `202` | ready 프로필·설치된 Seed-VC 필요 |
| `list_singing_lullabies` | `GET .../conversions` | `200` | 최근 변환 순 목록 |
| `get_singing_lullaby` | `GET .../conversions/{conversion_id}` | `200` | 상태·파라미터·결과 URL |
| `get_singing_lullaby_audio` | `GET .../conversions/{conversion_id}/audio` | `200` | 44.1kHz 변환 WAV |
| `create_singing_lullaby_playback_plan` | `POST .../{conversion_id}/playback-plan` | `200` | 반복·타이머 실행 계획 |
| `delete_singing_lullaby` | `DELETE .../conversions/{conversion_id}` | `204` | 결과 WAV와 메타데이터 삭제 |

생성 본문의 `diffusion_steps`는 생략 시 서버 기본값 10입니다. 4~10은 CPU 시연 속도, 30~50은
품질 우선 설정입니다. `semitone_shift`는 -12~12 범위입니다. 서버는 최대 3초 구간으로 나눠
순차 변환한 뒤 20ms crossfade로 결합합니다. `GET /health/ready`의
`seedvc_runtime_ready=false`이면 생성 버튼을 비활성화합니다.

현재 카탈로그는 CC0 1.0으로 공개된 실제 여성 무반주 가창 `작은별_영문.wav`의 9초 구간을
포함합니다. 프론트는 `composition_license`, `recording_license`, `attribution`을 원곡 상세에
표시해야 합니다. 서버는 시작할 때 카탈로그 SHA-256과 경로 이탈을 검증합니다.

## 11. 변경·검증 규칙

- 백엔드는 스키마 변경 시 `scripts/export_openapi.py`를 실행해 `docs/openapi.json`을 함께 커밋합니다.
- 계약 스냅샷이 코드와 다르면 테스트가 실패합니다.
- 기존 enum 값 삭제, 필수 필드 추가, 타입 변경, 성공 status 변경은 호환성 파괴 변경입니다.
- 선택 필드 추가와 새 endpoint 추가는 원칙적으로 하위 호환 변경입니다.
- 프론트는 알 수 없는 오류 코드를 일반 오류로 처리하는 fallback을 둡니다.
- Swagger의 성공·오류 예제는 개발 편의를 위한 값이며 실제 UUID로 고정하지 않습니다.

```bash
uv run ruff check .
uv run python -m pytest -q
uv run python -m scripts.export_openapi
git diff --exit-code docs/openapi.json
```
