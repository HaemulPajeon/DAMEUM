"""
S2+S3+S4: for each long-form raw WAV (selected by select_subset.py), run
zero-shot Whisper-small in long-form/timestamped mode, align its hypothesis
segments against the ground-truth Transcript (global difflib alignment +
linear interpolation between matching anchors), slice the audio into
Whisper-trainable (<=30s) clips, and write per-split manifests. The zero-shot
hyp text saved alongside each clip's aligned ground truth doubles as the S4
baseline CER data (see compute_baseline_cer.py).
"""
import difflib
import json
import os
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import torch
from transformers import pipeline

BASE = Path(os.environ.get("DAMEUM_STT_DATA_DIR", "./data"))
RAW_FILES_MANIFEST = BASE / "manifests" / "raw_files.jsonl"
CLIPS_DIR = BASE / "clips"
MANIFEST_DIR = BASE / "manifests"

TARGET_SR = 16000
MODEL_ID = "openai/whisper-tiny"  # hackathon time crunch: bootstrap/alignment model only,
# final LoRA fine-tune (train_lora.py) still targets whisper-small per the plan.
MAX_CLIP_SEC = 30.0
MIN_CLIP_SEC = 0.3
# Hard time budget: pick the SHORTEST already-extracted raw files first, per
# split, until this many hours are reached, instead of processing all 32.57h.
HOUR_BUDGET = {"train": 2.8, "val": 0.6, "test": 0.6}
# Sanity cap on Korean chars/sec of aligned ground truth. When several
# consecutive hyp segments are too garbled for difflib to anchor against the
# transcript, the interpolation-based mapper can dump a whole run of orphaned
# transcript words onto one short clip (observed: 7 words assigned to a 2s
# clip). That's actively wrong supervision, worse than just dropping the
# segment, so segments implausibly dense for their duration are discarded.
MAX_CHARS_PER_SEC = 8.0
# Direct energy-based silence gate. Discovered by listening to actual output:
# whisper-tiny's no_speech_threshold is much less reliable than small's, so
# on word-list recordings (long pauses between words) it still emits hyp text
# for pure-silence spans, and the aligner dutifully pairs that with real
# ground-truth words -- 53% of a sampled batch turned out to be true silence
# (rms ~0.00007, identical across unrelated files) paired with real text.
# Real speech in this corpus measured rms >= ~0.005; silence sits ~70x lower,
# so this threshold cleanly separates the two regardless of which Whisper
# size is used for the bootstrap pass.
MIN_CLIP_RMS = 0.001


def build_anchors(matching_blocks):
    anchors = []
    for a, b, size in matching_blocks:
        if size == 0:
            continue
        anchors.append((a, b))
        anchors.append((a + size, b + size))
    return anchors


def map_pos(pos, anchors):
    if not anchors:
        return 0
    if pos <= anchors[0][0]:
        return anchors[0][1]
    if pos >= anchors[-1][0]:
        return anchors[-1][1]
    for i in range(len(anchors) - 1):
        a0, b0 = anchors[i]
        a1, b1 = anchors[i + 1]
        if a0 <= pos <= a1:
            if a1 == a0:
                return b0
            ratio = (pos - a0) / (a1 - a0)
            return int(b0 + ratio * (b1 - b0))
    return anchors[-1][1]


def align_chunks_to_transcript(chunks, transcript):
    """chunks: list of {"timestamp": (start,end), "text": str} from the HF ASR
    pipeline, in time order. Returns list of dicts with start/end/hyp_text/gt_text."""
    hyp_texts = [c["text"] for c in chunks]
    hyp_concat = "".join(hyp_texts)
    offsets = []
    pos = 0
    for t in hyp_texts:
        offsets.append((pos, pos + len(t)))
        pos += len(t)

    sm = difflib.SequenceMatcher(None, hyp_concat, transcript, autojunk=False)
    anchors = build_anchors(sm.get_matching_blocks())

    results = []
    prev_gt_end = 0
    for chunk, (h_start, h_end) in zip(chunks, offsets):
        start, end = chunk["timestamp"]
        if end is None:
            end = start + MAX_CLIP_SEC
        gt_start = max(map_pos(h_start, anchors), prev_gt_end)
        gt_end = max(map_pos(h_end, anchors), gt_start)
        gt_text = transcript[gt_start:gt_end].strip()
        prev_gt_end = gt_end
        results.append(
            {
                "start": start,
                "end": end,
                "hyp_text": chunk["text"].strip(),
                "gt_text": gt_text,
            }
        )
    return results


def process_file(row, asr):
    raw_path = row["raw_audio_path"]
    audio, _ = librosa.load(raw_path, sr=TARGET_SR, mono=True)

    # NOTE: deliberately do NOT pass chunk_length_s/stride_length_s -- that
    # triggers the ASR pipeline's naive fixed-window chunking, which HF's own
    # warning flags as "very experimental with seq2seq models". A smoke test
    # confirmed it silently drops most of a long file's audio (a 206s file
    # yielded only 2 chunks covering its last 38s) and can wedge the model into
    # a repetition-loop hallucination ("칵-칵-칵-..." x150). Omitting those args
    # routes through Whisper's proper built-in long-form generate() algorithm
    # instead, which produced 28 well-formed chunks covering the same file.
    # The anti-hallucination generate_kwargs (temperature fallback ladder,
    # compression_ratio/logprob thresholds) are the same safeguards from the
    # original Whisper long-form decoding algorithm.
    out = asr(
        {"array": audio, "sampling_rate": TARGET_SR},
        return_timestamps=True,
        generate_kwargs={
            "language": "korean",
            "task": "transcribe",
            "condition_on_prev_tokens": False,
            "temperature": (0.0, 0.5),  # shortened fallback ladder (hackathon time crunch)
            "compression_ratio_threshold": 1.35,
            "logprob_threshold": -1.0,
            "no_speech_threshold": 0.6,
        },
    )
    chunks = out.get("chunks") or []
    if not chunks:
        return []

    aligned = align_chunks_to_transcript(chunks, row["transcript"])

    # Per-file outlier guard: when several consecutive hyp segments are too
    # garbled to anchor, the interpolation mapper can dump a whole run of
    # orphaned transcript words onto one segment. A fixed chars/sec cap misses
    # this (the dump can still look like a "plausible" rate in isolation), but
    # comparing against this same file's OTHER segments catches it -- observed
    # case: sibling segments got 14/10 gt chars, the bad one got 119.
    gt_lens = [len(s["gt_text"]) for s in aligned if s["gt_text"]]
    median_len = sorted(gt_lens)[len(gt_lens) // 2] if gt_lens else 0
    outlier_cap = max(3 * median_len, 20)

    split = row["split"]
    clip_dir = CLIPS_DIR / split
    clip_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows = []
    for i, seg in enumerate(aligned):
        dur = seg["end"] - seg["start"]
        if dur < MIN_CLIP_SEC or dur > MAX_CLIP_SEC + 2:
            continue
        if not seg["gt_text"]:
            continue
        if len(seg["gt_text"]) / max(dur, 0.1) > MAX_CHARS_PER_SEC:
            continue
        if len(seg["gt_text"]) > outlier_cap:
            continue
        s_idx = int(seg["start"] * TARGET_SR)
        e_idx = int(seg["end"] * TARGET_SR)
        clip_audio = audio[s_idx:e_idx]
        if len(clip_audio) < int(MIN_CLIP_SEC * TARGET_SR):
            continue
        rms = float(np.sqrt(np.mean(clip_audio.astype(np.float64) ** 2))) if len(clip_audio) else 0.0
        if rms < MIN_CLIP_RMS:
            continue
        utt_id = f"{row['raw_id']}_{i:03d}"
        clip_path = clip_dir / f"{utt_id}.wav"
        sf.write(clip_path, clip_audio, TARGET_SR, subtype="PCM_16")
        manifest_rows.append(
            {
                "utt_id": utt_id,
                "raw_id": row["raw_id"],
                "speaker_key": row["speaker_key"],
                "split": split,
                "start_sec": seg["start"],
                "end_sec": seg["end"],
                "duration": dur,
                "gt_text": seg["gt_text"],
                "hyp_text_zero_shot": seg["hyp_text"],
                "clip_path": str(clip_path),
            }
        )
    return manifest_rows


def select_within_budget(rows):
    by_split = {}
    for r in rows:
        by_split.setdefault(r["split"], []).append(r)
    selected = []
    for split, split_rows in by_split.items():
        split_rows.sort(key=lambda r: r["playtime_sec"])  # shortest first: more files, faster
        budget_sec = HOUR_BUDGET.get(split, 0) * 3600
        acc = 0.0
        for r in split_rows:
            if acc >= budget_sec:
                break
            selected.append(r)
            acc += r["playtime_sec"]
        print(f"  budget {split}: {acc/3600:.2f}h / {HOUR_BUDGET.get(split,0)}h target, {sum(1 for r in selected if r['split']==split)} files")
    return selected


def main():
    all_rows = [json.loads(l) for l in open(RAW_FILES_MANIFEST, encoding="utf-8")]
    print(f"{len(all_rows)} raw files available, applying hour budget {HOUR_BUDGET}...")
    rows = select_within_budget(all_rows)
    print(f"{len(rows)} raw files selected to process")

    device = 0 if torch.cuda.is_available() else -1
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    print(f"Loading {MODEL_ID} (device={'cuda' if device==0 else 'cpu'}, dtype={dtype})...")
    asr = pipeline(
        "automatic-speech-recognition",
        model=MODEL_ID,
        device=device,
        torch_dtype=dtype,
    )

    manifests = {"train": [], "val": [], "test": []}
    for idx, row in enumerate(rows):
        print(f"[{idx+1}/{len(rows)}] {row['raw_id']} ({row['playtime_sec']/60:.1f} min, split={row['split']})")
        try:
            seg_rows = process_file(row, asr)
        except Exception as e:
            print(f"  ERROR on {row['raw_id']}: {e}")
            continue
        manifests[row["split"]].extend(seg_rows)
        print(f"  -> {len(seg_rows)} clips")

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    for split, seg_rows in manifests.items():
        path = MANIFEST_DIR / f"manifest_{split}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for r in seg_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        total_hours = sum(r["duration"] for r in seg_rows) / 3600
        print(f"{split}: {len(seg_rows)} clips, {total_hours:.2f}h -> {path}")


if __name__ == "__main__":
    main()
