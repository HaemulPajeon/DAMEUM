"""S4: aggregate zero-shot Whisper-small CER/WER per split from the manifests
produced by segment_and_align.py. hyp_text_zero_shot/gt_text pairs were
captured during segmentation, so this is pure aggregation, no inference."""
import json
import os
from pathlib import Path

import jiwer

MANIFEST_DIR = Path(os.environ.get("DAMEUM_STT_DATA_DIR", "./data")) / "manifests"


def main():
    results = {}
    for split in ("train", "val", "test"):
        path = MANIFEST_DIR / f"manifest_{split}.jsonl"
        if not path.exists():
            continue
        rows = [json.loads(l) for l in open(path, encoding="utf-8")]
        refs = [r["gt_text"] for r in rows]
        hyps = [r["hyp_text_zero_shot"] for r in rows]
        cer = jiwer.cer(refs, hyps)
        wer = jiwer.wer(refs, hyps)
        total_hours = sum(r["duration"] for r in rows) / 3600
        results[split] = {
            "n_clips": len(rows),
            "hours": round(total_hours, 3),
            "zero_shot_cer": round(cer, 4),
            "zero_shot_wer": round(wer, 4),
        }
        print(f"{split}: {len(rows)} clips, {total_hours:.2f}h, CER={cer:.4f}, WER={wer:.4f}")

    with open(MANIFEST_DIR / "baseline_cer.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Written to {MANIFEST_DIR / 'baseline_cer.json'}")


if __name__ == "__main__":
    main()
