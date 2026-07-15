"""S7: wav -> corrected text inference function for downstream TTS hookup."""
import os
from pathlib import Path

import librosa
import torch
from peft import PeftModel
from transformers import WhisperForConditionalGeneration, WhisperProcessor

# Defaults to the adapter checked into this repo (../outputs/...); override with
# DAMEUM_STT_ADAPTER_DIR if you're pointing at a different/retrained adapter.
_DEFAULT_ADAPTER_DIR = Path(__file__).resolve().parent.parent / "outputs" / "whisper-small-lora-dysarthria"
ADAPTER_DIR = Path(os.environ.get("DAMEUM_STT_ADAPTER_DIR", str(_DEFAULT_ADAPTER_DIR)))
MODEL_ID = "openai/whisper-small"

_processor = None
_model = None
_device = "cuda" if torch.cuda.is_available() else "cpu"


def _load():
    global _processor, _model
    if _model is not None:
        return
    _processor = WhisperProcessor.from_pretrained(str(ADAPTER_DIR))
    base_model = WhisperForConditionalGeneration.from_pretrained(MODEL_ID)
    _model = PeftModel.from_pretrained(base_model, str(ADAPTER_DIR)).to(_device)
    _model.eval()


def transcribe(wav_path: str) -> str:
    """Load a wav file (any sample rate) and return the corrected Korean transcript."""
    _load()
    audio, _ = librosa.load(wav_path, sr=16000, mono=True)
    input_features = _processor.feature_extractor(audio, sampling_rate=16000).input_features
    input_features = torch.tensor(input_features).to(_device)
    with torch.no_grad():
        generated_ids = _model.generate(input_features, language="korean", task="transcribe")
    return _processor.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]


if __name__ == "__main__":
    import sys

    # This Windows env's default stdout encoding is cp949, not UTF-8 -- printing
    # Korean text without this would silently mis-encode it (garbled output in
    # any UTF-8-expecting terminal/log), regardless of console codepage.
    sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) != 2:
        print("usage: python infer.py <wav_path>")
        raise SystemExit(1)
    print(transcribe(sys.argv[1]))
