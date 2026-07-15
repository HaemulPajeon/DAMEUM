# 담음 REST API 연동 규격

기본 URL은 `http://127.0.0.1:8000`입니다. `/v1` API는 `X-API-Key` 요청 헤더가 필요합니다. JSON 오류 응답은 `detail.code`와 사용자 표시용 `detail.message`를 제공합니다.

## 권장 연동 순서

1. 목소리 프로필 생성
2. 문장과 음성 샘플 5~20개 등록
3. 프로필 미리듣기 생성 작업 요청
4. 미리듣기 확인 후 책 생성
5. 페이지 이미지 등록
6. 페이지 녹음 업로드 및 추론 작업 조회
7. 재생 manifest로 원본/재합성 오디오 재생

## 목소리 프로필

| Method | Path | 설명 |
|---|---|---|
| `POST` | `/v1/voice-profiles` | 프로필과 음성 소유자 동의 등록 |
| `GET` | `/v1/voice-profiles` | 프로필 목록 |
| `GET` | `/v1/voice-profiles/{id}` | 프로필·샘플 수·미리듣기 상태 |
| `DELETE` | `/v1/voice-profiles/{id}` | 사용하지 않는 프로필과 모든 샘플 삭제 |
| `POST` | `/v1/voice-profiles/{id}/samples` | `multipart/form-data`: `prompt_text`, `audio` |
| `GET` | `/v1/voice-profiles/{id}/samples` | 샘플 목록 |
| `DELETE` | `/v1/voice-profiles/{id}/samples/{sample_id}` | 샘플 삭제 |
| `POST` | `/v1/voice-profiles/{id}/preview` | 미리듣기 생성/재생성 작업 |
| `GET` | `/v1/voice-profiles/{id}/preview/audio` | 미리듣기 WAV |

프로필 생성의 `source_kind`는 `pre_illness`, `family_donation`, `current_voice` 중 하나입니다. `consent_confirmed`는 반드시 `true`여야 합니다. 샘플이 변경되면 프로필은 다시 `draft`가 되며 미리듣기 재생성을 완료해야 페이지 녹음에 사용할 수 있습니다.

## 동화책과 페이지 녹음

| Method | Path | 설명 |
|---|---|---|
| `POST` | `/v1/books` | 책과 페이지별 텍스트 생성 |
| `GET` | `/v1/books` | 책 목록과 페이지 상태 |
| `GET` | `/v1/books/{id}` | 페이지 텍스트·이미지·녹음 결과 |
| `DELETE` | `/v1/books/{id}` | 책과 관련 미디어 삭제 |
| `PUT` | `/v1/books/{id}/pages/{number}/image` | `multipart/form-data`: `image` |
| `PUT` | `/v1/books/{id}/pages/{number}/recording` | `multipart/form-data`: `profile_id`, `audio` |
| `GET` | `/v1/books/{id}/pages/{number}/audio?source=original` | 원본 녹음 |
| `GET` | `/v1/books/{id}/pages/{number}/audio?source=clarified` | 재합성 WAV |
| `GET` | `/v1/books/{id}/playback-manifest` | 수동 재생·프리패치용 URL 목록 |

같은 페이지에 `PUT recording`을 다시 호출하면 해당 페이지의 `version`만 증가하고 다른 페이지는 변경되지 않습니다. 이전 추론이 늦게 끝나더라도 버전 검증에서 폐기되어 새 녹음을 덮어쓰지 않습니다.

`recording` 결과에는 다음 값이 포함됩니다.

- `transcript`: faster-whisper의 STT 결과
- `corrected_text`: 로컬 LLM이 복원한 문장
- `emotion`, `emotion_score`: 한국어 감정 분류 결과
- `original_url`, `clarified_url`: 프론트 토글용 재생 URL

## 자장가와 콘텐츠 라이브러리

| Method | Path | 설명 |
|---|---|---|
| `POST` | `/v1/lullabies` | 부모 음색의 부드러운 낭독 생성 |
| `GET` | `/v1/lullabies` | 자장가 목록과 반복·타이머 설정 |
| `GET` | `/v1/lullabies/{id}` | 자장가 상세 |
| `GET` | `/v1/lullabies/{id}/audio` | 자장가 WAV |
| `DELETE` | `/v1/lullabies/{id}` | 자장가와 미디어 삭제 |
| `GET` | `/v1/library` | 책·자장가 통합 목록 |

`repeat_count`와 `timer_minutes`는 재생 정책입니다. 실제 루프와 타이머 중단은 오디오를 재생하는 프론트엔드에서 수행합니다.

## 비동기 작업

`POST preview`, `PUT recording`, `POST lullabies`는 `202 Accepted`와 `job_id`를 반환합니다.

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/v1/jobs/{job_id}` | `queued`, `running`, `succeeded`, `failed` 상태 및 진행률 |

`failed`일 때 `error_code`는 분기 처리용이며 `error_message`는 로컬 사용자에게 표시할 수 있습니다. 대기열이 가득 차면 `503`과 `Retry-After: 30`을 반환합니다.

## 상태 확인

| Method | Path | 인증 | 설명 |
|---|---|---|---|
| `GET` | `/health/live` | 불필요 | 프로세스 생존 확인 |
| `GET` | `/health/ready` | 불필요 | 추론 backend, 모델 구성, 대기 작업 수 |
