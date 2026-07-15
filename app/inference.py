from __future__ import annotations

import gc
import math
import os
import re
import wave
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings

EMOTION_STYLE = {
    "기쁨": "warm, cheerful and affectionate",
    "당황": "gentle and slightly surprised",
    "분노": "calm and firm without sounding threatening",
    "불안": "soft, reassuring and steady",
    "상처": "tender, comforting and empathetic",
    "슬픔": "soft, calm and comforting",
    "중립": "warm, clear and natural",
}


class InferencePipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._stt: Any = None
        self._emotion_tokenizer: Any = None
        self._emotion_model: Any = None
        self._tts: Any = None

    def transcribe(self, audio_path: Path, expected_text: str | None = None) -> str:
        if self.settings.inference_backend == "mock":
            return expected_text or "사랑하는 우리 아이야, 오늘도 행복한 하루 보내자."
        if self._stt is None:
            from faster_whisper import WhisperModel

            self._stt = WhisperModel(
                self.settings.stt_model,
                device="cpu",
                compute_type="int8",
                cpu_threads=self.settings.cpu_threads,
                num_workers=1,
            )
        segments, _ = self._stt.transcribe(
            str(audio_path),
            language="ko",
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        transcript = " ".join(segment.text.strip() for segment in segments).strip()
        if not transcript:
            raise RuntimeError("음성에서 발화를 인식하지 못했습니다")
        return transcript

    def correct_sentence(self, transcript: str, expected_text: str | None = None) -> str:
        if self.settings.inference_backend == "mock":
            return expected_text or transcript
        context = expected_text or "제공되지 않음"
        prompt = (
            "구음장애가 있는 한국어 화자의 STT 오류를 복원하세요. "
            "동화책 원문이 제공되고 STT가 그 원문을 읽으려 한 발화라면, "
            "맞춤법과 어미를 포함해 동화책 원문을 한 글자도 바꾸지 말고 출력하세요. "
            "서로 다른 내용일 때만 STT의 의도를 보존해 최소한으로 교정하세요. "
            "예시: 원문 '달님이 환하게 웃었어요.', STT '달님이 환하게 우떠요'이면 "
            "'달님이 환하게 웃었어요.'를 출력합니다. 설명과 따옴표 없이 결과 문장만 출력하세요.\n"
            f"동화책 원문: {context}\nSTT 결과: {transcript}"
        )
        with httpx.Client(timeout=httpx.Timeout(120.0, connect=5.0)) as client:
            response = client.post(
                f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
                json={
                    "model": self.settings.llm_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "당신은 한국어 동화책 낭독 발화 복원기입니다. "
                                "원문과 같은 의도의 손상된 STT는 원문 그대로 복원하고, "
                                "설명 없이 복원 문장만 답합니다."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "top_p": 0.8,
                    "max_tokens": 256,
                    "chat_template_kwargs": {"enable_thinking": False},
                },
            )
            response.raise_for_status()
        corrected = response.json()["choices"][0]["message"]["content"].strip()
        corrected = re.sub(r"<think>.*?</think>", "", corrected, flags=re.DOTALL).strip()
        corrected = corrected.strip('"').strip()
        if not corrected or len(corrected) > 3000:
            raise RuntimeError("문장 교정 결과가 유효하지 않습니다")
        if expected_text:
            compact_corrected = re.sub(r"[^0-9A-Za-z가-힣]", "", corrected)
            compact_expected = re.sub(r"[^0-9A-Za-z가-힣]", "", expected_text)
            if compact_corrected == compact_expected:
                # 내용이 일치하면 원문의 문장부호와 띄어쓰기까지 보존한다.
                return expected_text.strip()
        return corrected

    def classify_emotion(self, text: str) -> tuple[str, float]:
        if self.settings.inference_backend == "mock":
            return "기쁨", 0.99
        if self._emotion_model is None:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self._emotion_tokenizer = AutoTokenizer.from_pretrained(self.settings.emotion_model)
            self._emotion_model = AutoModelForSequenceClassification.from_pretrained(
                self.settings.emotion_model
            )
            self._emotion_model.eval()
        import torch

        inputs = self._emotion_tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
        with torch.inference_mode():
            probabilities = torch.softmax(self._emotion_model(**inputs).logits[0], dim=-1)
        index = int(torch.argmax(probabilities).item())
        score = float(probabilities[index].item())
        raw_label = str(self._emotion_model.config.id2label.get(index, index))
        return self._normalize_emotion(raw_label), score

    def synthesize(
        self,
        text: str,
        reference_path: Path,
        output_path: Path,
        emotion: str = "중립",
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.settings.inference_backend == "mock":
            self._write_mock_wav(output_path, duration=max(1.5, min(8.0, len(text) * 0.08)))
            return
        if self._tts is None:
            from voxcpm import VoxCPM

            # CPU와 Windows에서 torch.compile/Triton 경로를 사용하지 않는다.
            self._tts = VoxCPM.from_pretrained(
                self.settings.voxcpm_model,
                device="cpu",
                optimize=False,
                load_denoiser=False,
            )
        import soundfile as sf

        style = EMOTION_STYLE.get(emotion, EMOTION_STYLE["중립"])
        waveform = self._tts.generate(
            text=f"({style}){text}",
            reference_wav_path=str(reference_path),
            cfg_value=2.0,
            inference_timesteps=10,
            normalize=True,
            denoise=False,
            retry_badcase=True,
        )
        sf.write(output_path, waveform, self._tts.tts_model.sample_rate)
        output_path.chmod(0o600)

    def release_models(self) -> None:
        if not self.settings.unload_models_after_job:
            return
        self._stt = None
        self._emotion_tokenizer = None
        self._emotion_model = None
        self._tts = None
        gc.collect()

    @staticmethod
    def _normalize_emotion(label: str) -> str:
        normalized = label.lower().replace("label_", "")
        aliases = {
            "0": "기쁨",
            "1": "슬픔",
            "2": "분노",
            "3": "불안",
            "4": "당황",
            "5": "상처",
            "joy": "기쁨",
            "surprise": "당황",
            "anger": "분노",
            "anxiety": "불안",
            "hurt": "상처",
            "sadness": "슬픔",
            "neutral": "중립",
        }
        for key, value in aliases.items():
            if key == normalized or key in normalized:
                return value
        for emotion in EMOTION_STYLE:
            if emotion in label:
                return emotion
        return "중립"

    @staticmethod
    def _write_mock_wav(path: Path, duration: float) -> None:
        sample_rate = 16000
        amplitude = 5000
        frames = bytearray()
        for index in range(int(sample_rate * duration)):
            sample = int(amplitude * math.sin(2 * math.pi * 220 * index / sample_rate))
            frames.extend(sample.to_bytes(2, byteorder="little", signed=True))
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            output.writeframes(frames)
        path.chmod(0o600)


def configure_cpu_threads(settings: Settings) -> None:
    os.environ.setdefault("OMP_NUM_THREADS", str(settings.cpu_threads))
    os.environ.setdefault("MKL_NUM_THREADS", str(settings.cpu_threads))
    try:
        import torch

        torch.set_num_threads(settings.cpu_threads)
        torch.set_num_interop_threads(1)
    except (ImportError, RuntimeError):
        pass
