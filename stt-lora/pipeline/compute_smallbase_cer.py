"""Fair-comparison baseline: whisper-small zero-shot (no LoRA) on the same
test manifest, to isolate the LoRA fine-tuning effect from the tiny->small
model-capacity jump already baked into baseline_cer.json (that one was
measured with whisper-tiny during the hackathon-speed segmentation pass)."""
import json
import os
from pathlib import Path

import jiwer
import librosa
import torch
from transformers import WhisperForConditionalGeneration, WhisperProcessor

MANIFEST_DIR = Path(os.environ.get("DAMEUM_STT_DATA_DIR", "./data")) / "manifests"
MODEL_ID = "openai/whisper-small"


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = WhisperProcessor.from_pretrained(MODEL_ID, language="korean", task="transcribe")
    model = WhisperForConditionalGeneration.from_pretrained(MODEL_ID).to(device)
    model.eval()

    rows = [json.loads(l) for l in open(MANIFEST_DIR / "manifest_test.jsonl", encoding="utf-8")]
    refs, hyps = [], []
    for r in rows:
        audio, _ = librosa.load(r["clip_path"], sr=16000, mono=True)
        input_features = processor.feature_extractor(audio, sampling_rate=16000).input_features
        input_features = torch.tensor(input_features).to(device)
        with torch.no_grad():
            generated_ids = model.generate(input_features, language="korean", task="transcribe")
        pred = processor.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
        refs.append(r["gt_text"])
        hyps.append(pred)

    cer = jiwer.cer(refs, hyps)
    wer = jiwer.wer(refs, hyps)
    print(f"whisper-small ZERO-SHOT (no LoRA) test CER={cer:.4f}, WER={wer:.4f} (n={len(rows)})")
    with open(MANIFEST_DIR / "smallbase_test_cer.json", "w", encoding="utf-8") as f:
        json.dump({"cer": cer, "wer": wer, "n_clips": len(rows)}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
