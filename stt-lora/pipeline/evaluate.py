"""S6: evaluate the LoRA fine-tuned model on manifest_test.jsonl and compare
against the zero-shot baseline CER/WER captured in baseline_cer.json."""
import json
import os
from pathlib import Path

import jiwer
import librosa
import torch
from peft import PeftModel
from transformers import WhisperForConditionalGeneration, WhisperProcessor

# MANIFEST_DIR holds the (large, not checked into git) manifests produced by
# select_subset.py/segment_and_align.py -- point this at your local data dir.
MANIFEST_DIR = Path(os.environ.get("DAMEUM_STT_DATA_DIR", "./data")) / "manifests"
_DEFAULT_ADAPTER_DIR = Path(__file__).resolve().parent.parent / "outputs" / "whisper-small-lora-dysarthria"
ADAPTER_DIR = Path(os.environ.get("DAMEUM_STT_ADAPTER_DIR", str(_DEFAULT_ADAPTER_DIR)))
MODEL_ID = "openai/whisper-small"


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = WhisperProcessor.from_pretrained(str(ADAPTER_DIR))
    base_model = WhisperForConditionalGeneration.from_pretrained(MODEL_ID)
    model = PeftModel.from_pretrained(base_model, str(ADAPTER_DIR)).to(device)
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
    print(f"Fine-tuned test CER={cer:.4f}, WER={wer:.4f} (n={len(rows)})")

    baseline_path = MANIFEST_DIR / "baseline_cer.json"
    if baseline_path.exists():
        baseline = json.load(open(baseline_path, encoding="utf-8")).get("test", {})
        print(f"Zero-shot baseline test CER={baseline.get('zero_shot_cer')}, WER={baseline.get('zero_shot_wer')}")
        if "zero_shot_cer" in baseline:
            delta = baseline["zero_shot_cer"] - cer
            print(f"CER improvement: {delta:+.4f} ({'better' if delta > 0 else 'worse'})")

    with open(MANIFEST_DIR / "finetuned_test_results.json", "w", encoding="utf-8") as f:
        json.dump(
            {"cer": cer, "wer": wer, "n_clips": len(rows), "predictions": [
                {"gt_text": r, "pred_text": h} for r, h in zip(refs, hyps)
            ]},
            f, ensure_ascii=False, indent=2,
        )


if __name__ == "__main__":
    main()
