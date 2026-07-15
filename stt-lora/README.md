# STT LoRA — 구음장애 발화 인식 파인튜닝

Whisper-small을 AI-Hub `013.구음장애 음성인식 데이터`(뇌신경장애 서브셋)로 LoRA 파인튜닝하는 파이프라인. 목표는 구음장애(마비말장애) 발화에 대한 STT 정확도 개선.

## 결과 (프로토타입, 해커톤 시간 제약 하 실행)

| | CER | WER |
|---|---|---|
| 제로샷 baseline (whisper-small) | 64.3% | 60.3% |
| LoRA 파인튜닝 후 | **53.6%** | **51.5%** |

test 125개 클립 기준, train 24분/val 14분/test 12분 분량의 매우 작은 서브셋으로 학습한 결과입니다. 파이프라인이 동작하고 파인튜닝이 방향성 있는 개선을 만든다는 것을 확인한 **프로토타입**이며, 프로덕션 정확도가 아닙니다. 더 큰 데이터(원본 계획은 262시간 중 25~30시간)로 재학습하면 개선 여지가 있습니다.

## ⚠️ 백엔드 통합 전 확인 필요: STT 런타임 포맷 불일치

`feat/dameum-fastapi` 브랜치의 `app/inference.py`는 **faster-whisper**(CTranslate2 포맷)를 씁니다. 이 저장소의 어댑터는 HuggingFace `transformers` + `peft` 포맷이라 **그대로 못 꽂습니다.** 통합하려면 둘 중 하나:

1. LoRA 가중치를 베이스 모델에 merge(`PeftModel.merge_and_unload()`) 후 `ct2-transformers-converter`로 CTranslate2 포맷 변환 → faster-whisper에서 로드
2. `app/inference.py`의 STT 백엔드를 이 파인튜닝 모델 사용 시엔 `transformers`+`peft` 직접 호출로 분기

성능/메모리 트레이드오프가 있어서 백엔드 담당자와 상의 후 결정하는 게 좋을 것 같습니다.

## 데이터

⚠️ AI-Hub 데이터(원본 zip, 추출 오디오, 화자 메타데이터)는 환자 개인정보가 포함돼 있어 **이 저장소에 포함하지 않습니다.** `data/` 아래에 로컬로 준비하세요 (AI-Hub 승인 후 다운로드, `.gitignore` 처리됨).

```
data/
  013.구음장애 음성인식 데이터/...   # AI-Hub 원본 (TL01/TS01 라벨+오디오 zip)
  manifests/                          # select_subset.py, segment_and_align.py 출력
  subset/raw/, clips/                 # 추출/세그멘테이션된 오디오
```

환경변수 `DAMEUM_STT_DATA_DIR`로 위치 지정 (기본값 `./data`).

## 파이프라인 (순서대로 실행)

1. `pipeline/select_subset.py` — 화자 다양성 기준 서브셋 선정 + 화자단위 train/val/test 분할 + 원본 zip에서 부분 압축해제
2. `pipeline/segment_and_align.py` — 긴 원본 오디오(라벨에 구간 타임스탬프 없음)를 학습 가능한 clip으로 세그멘테이션. 제로샷 Whisper로 타임스탬프+텍스트를 얻고, 원본 Transcript와 정렬해서 (오디오 조각, 정답 텍스트) 쌍 생성. 무음/이상치 정렬 필터 포함.
3. `pipeline/compute_baseline_cer.py` — 세그멘테이션 단계에서 나온 제로샷 예측으로 baseline CER/WER 집계 (별도 추론 불필요)
4. `pipeline/train_lora.py` — whisper-small + LoRA(r=32, alpha=64, target=q_proj·v_proj) 파인튜닝
5. `pipeline/evaluate.py` — test set으로 파인튜닝 모델 CER/WER 평가, baseline과 비교
6. `pipeline/infer.py` — `transcribe(wav_path) -> str` 함수. 백엔드/TTS 연동 지점.

```bash
export DAMEUM_STT_DATA_DIR=/path/to/data   # Windows: $env:DAMEUM_STT_DATA_DIR
python pipeline/select_subset.py
python pipeline/segment_and_align.py
python pipeline/compute_baseline_cer.py
python pipeline/train_lora.py
python pipeline/evaluate.py
```

## 추론 사용법

```python
from pipeline.infer import transcribe
text = transcribe("path/to/audio.wav")  # 16kHz 아니어도 내부에서 리샘플
```

기본적으로 이 저장소에 커밋된 `outputs/whisper-small-lora-dysarthria/` 어댑터를 씁니다. 다른 어댑터를 쓰려면 `DAMEUM_STT_ADAPTER_DIR` 환경변수로 지정하세요.

## 환경

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install transformers peft accelerate datasets jiwer soundfile librosa
```

GPU 8GB+ 권장 (RTX 4070 Laptop 기준 학습 완료, `train_lora.py`의 `BATCH_SIZE`/`GRAD_ACCUM`이 그 기준으로 맞춰져 있음).

## 알려진 한계 (다음에 손볼 것)

- 학습 데이터가 24분으로 매우 작음 — 원래 계획한 25~30시간 서브셋으로 재실행 필요
- `segment_and_align.py`의 정렬은 forced alignment가 아니라 제로샷 Whisper 예측 기반 휴리스틱이라, 일부 라벨이 부정확할 수 있음 (무음/이상치 필터로 상당 부분 제거하지만 완벽하지 않음)
- val set이 학습 중 체크포인트 선택에 쓰이지 않음(시간 제약으로 생략) — 여러 체크포인트 중 최선을 고르는 로직 없음
- learning_rate=1e-3으로 첫 학습 시도가 gradient explosion으로 완전히 붕괴한 적 있음(CER 111%, 모든 출력이 "."로 collapse). 1e-4 + warmup으로 해결했지만, 데이터가 늘어나면 하이퍼파라미터 재검증 필요
