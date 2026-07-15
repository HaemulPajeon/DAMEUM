"""
S1 (data-plan step 1): select a ~25-30h speaker-diverse subset of the 262h
뇌신경장애 corpus, split by speaker into train/val/test, and extract only the
selected raw WAV files (flat, ASCII-only filenames) out of the 26.92GB zip.

All Korean text is handled only inside Python (zipfile/json), never passed as
a Bash/CLI argument -- this host's Git Bash mangles multibyte args, which
previously caused a real data-loss bug in aihubshell's merge step.
"""
import json
import os
import random
import re
import zipfile
from pathlib import Path

# Point this at your local AI-Hub download (see stt-lora/README.md) -- the raw
# zips/audio are large and patient-derived, so they are never checked into git.
BASE = Path(os.environ.get("DAMEUM_STT_DATA_DIR", "./data"))
LABEL_ZIP = BASE / "013.구음장애 음성인식 데이터" / "01.데이터" / "1.Training" / "라벨링데이터" / "TL01_뇌신경장애.zip"
AUDIO_ZIP = BASE / "013.구음장애 음성인식 데이터" / "01.데이터" / "1.Training" / "원천데이터" / "TS01_뇌신경장애.zip"
RAW_OUT = BASE / "subset" / "raw"
MANIFEST_DIR = BASE / "manifests"

TARGET_HOURS = 27.5          # midpoint of the agreed ~25-30h range
SPLIT_RATIOS = {"train": 0.70, "val": 0.15, "test": 0.15}
SEED = 42


def normalize(name: str) -> str:
    stem = name.rsplit("/", 1)[-1]
    stem = stem.rsplit(".", 1)[0]
    return stem.strip().lower()


def extract_speaker_code(file_id: str, sex: str, age, area: str) -> str:
    """Anchor on the known Sex/Age/Area fields (from Patient_info) to pull out
    the alphabetic speaker code token, regardless of how many session/sub-session
    digit groups precede it. Matches against the ORIGINAL-case file_id -- Sex/Area
    are upper-case in the source JSON, so case-insensitive matching is used."""
    stem = file_id.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    pattern = re.compile(rf"-([A-Za-z]+)-\d+(?:-\d+)?-{sex}-{age}-{area}", re.IGNORECASE)
    m = pattern.search(stem)
    return m.group(1).upper() if m else "UNK"


def load_labels():
    records = []
    with zipfile.ZipFile(LABEL_ZIP) as zf:
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            data = json.loads(zf.read(name))
            file_id = data["File_id"]
            sex = data["Patient_info"]["Sex"]
            age = data["Patient_info"]["Age"]
            area = data["Patient_info"]["Area"]
            code = extract_speaker_code(file_id, sex, age, area)
            speaker_key = f"{code}_{sex}{age}_{area}"
            category = name.split("/")[0] if "/" in name else ""
            play_time = float(data.get("playTime") or data["Meta_info"]["PlayTime"])
            records.append(
                {
                    "label_entry": name,
                    "file_id": file_id,
                    "transcript": data["Transcript"],
                    "speaker_key": speaker_key,
                    "sex": sex,
                    "age": age,
                    "area": area,
                    "category": category,
                    "playtime_sec": play_time,
                }
            )
    return records


def build_audio_lookup():
    with zipfile.ZipFile(AUDIO_ZIP) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
    lookup = {}
    for n in names:
        lookup.setdefault(normalize(n), n)
    return lookup


def match_audio(file_id: str, lookup: dict):
    key = normalize(file_id)
    if key in lookup:
        return lookup[key], "exact"
    stripped = re.sub(r"(중복\d*)$", "", key)
    if stripped in lookup:
        return lookup[stripped], "stripped-dup-suffix"
    candidates = [k for k in lookup if k.startswith(stripped[:-2])] if len(stripped) > 2 else []
    if len(candidates) == 1:
        return lookup[candidates[0]], "prefix-fallback"
    return None, "unmatched"


def select_speakers(records, target_hours):
    by_speaker = {}
    for r in records:
        by_speaker.setdefault(r["speaker_key"], []).append(r)

    speakers = []
    for key, recs in by_speaker.items():
        total_sec = sum(r["playtime_sec"] for r in recs)
        speakers.append(
            {
                "speaker_key": key,
                "sex": recs[0]["sex"],
                "area": recs[0]["area"],
                "n_files": len(recs),
                "total_hours": total_sec / 3600,
                "records": recs,
            }
        )

    # Bucket by (sex, area) for demographic diversity. Within each bucket, sort
    # ascending by hours (ties broken by a deterministic shuffle) so the picker
    # favors more, smaller speakers over a few huge ones -- hour distribution is
    # skewed (top speaker has 17h vs a 3.1h median), and picking large speakers
    # first starves val/test down to 1 speaker each.
    rng = random.Random(SEED)
    buckets = {}
    for s in speakers:
        buckets.setdefault((s["sex"], s["area"]), []).append(s)
    for b in buckets.values():
        rng.shuffle(b)
        b.sort(key=lambda s: s["total_hours"])

    bucket_keys = sorted(buckets.keys())
    rng.shuffle(bucket_keys)

    selected = []
    total = 0.0
    i = 0
    while total < target_hours:
        progressed = False
        for bk in bucket_keys:
            if i < len(buckets[bk]):
                sp = buckets[bk][i]
                selected.append(sp)
                total += sp["total_hours"]
                progressed = True
                if total >= target_hours:
                    break
        i += 1
        if not progressed:
            break  # exhausted all speakers
    return selected, total


def split_speakers(selected):
    """Greedily assign whole speakers to train/val/test, always adding the next
    speaker to whichever split is furthest below its target hour share."""
    total_hours = sum(s["total_hours"] for s in selected)
    targets = {k: v * total_hours for k, v in SPLIT_RATIOS.items()}
    current = {k: 0.0 for k in SPLIT_RATIOS}

    order = sorted(selected, key=lambda s: -s["total_hours"])  # largest first, better balance
    for sp in order:
        deficit = {k: targets[k] - current[k] for k in SPLIT_RATIOS}
        split = max(deficit, key=deficit.get)
        sp["split"] = split
        current[split] += sp["total_hours"]
    return current


def main():
    print("Loading label JSONs from zip...")
    records = load_labels()
    print(f"  {len(records)} label records, {len({r['speaker_key'] for r in records})} distinct speakers")

    print(f"Selecting speakers for ~{TARGET_HOURS}h target...")
    selected, total_hours = select_speakers(records, TARGET_HOURS)
    print(f"  selected {len(selected)} speakers, {total_hours:.2f}h total")

    split_hours = split_speakers(selected)
    for k, v in split_hours.items():
        print(f"  split={k}: {v:.2f}h, {sum(1 for s in selected if s['split'] == k)} speakers")

    print("Building audio zip filename lookup...")
    lookup = build_audio_lookup()

    for split in SPLIT_RATIOS:
        (RAW_OUT / split).mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    print("Matching + extracting selected raw audio files...")
    raw_rows = []
    unmatched = []
    with zipfile.ZipFile(AUDIO_ZIP) as zf:
        for spk_idx, sp in enumerate(selected):
            split = sp["split"]
            for file_idx, rec in enumerate(sp["records"]):
                entry, method = match_audio(rec["file_id"], lookup)
                if entry is None:
                    unmatched.append(rec["file_id"])
                    continue
                raw_id = f"spk{spk_idx:03d}_{sp['speaker_key']}_{file_idx:02d}"
                out_path = RAW_OUT / split / f"{raw_id}.wav"
                if not out_path.exists():
                    with zf.open(entry) as src, open(out_path, "wb") as dst:
                        dst.write(src.read())
                raw_rows.append(
                    {
                        "raw_id": raw_id,
                        "speaker_key": sp["speaker_key"],
                        "split": split,
                        "file_id": rec["file_id"],
                        "transcript": rec["transcript"],
                        "playtime_sec": rec["playtime_sec"],
                        "category": rec["category"],
                        "match_method": method,
                        "raw_audio_path": str(out_path),
                    }
                )

    with open(MANIFEST_DIR / "raw_files.jsonl", "w", encoding="utf-8") as f:
        for row in raw_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    speakers_summary = [
        {
            "speaker_key": s["speaker_key"],
            "sex": s["sex"],
            "area": s["area"],
            "split": s["split"],
            "n_files": s["n_files"],
            "total_hours": round(s["total_hours"], 3),
        }
        for s in selected
    ]
    with open(MANIFEST_DIR / "speakers.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "target_hours": TARGET_HOURS,
                "actual_total_hours": round(total_hours, 3),
                "split_hours": {k: round(v, 3) for k, v in split_hours.items()},
                "n_speakers": len(selected),
                "n_raw_files_extracted": len(raw_rows),
                "n_unmatched": len(unmatched),
                "unmatched_file_ids": unmatched,
                "speakers": speakers_summary,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Done. Extracted {len(raw_rows)} raw files, {len(unmatched)} unmatched.")
    print(f"Manifests written to {MANIFEST_DIR}")


if __name__ == "__main__":
    main()
