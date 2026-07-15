from __future__ import annotations

import platform
import subprocess
import tempfile
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

SAMPLE_RATE = 44100
ASSET_DIR = Path(__file__).resolve().parents[1] / "assets" / "lullabies"
TRACKS = {
    "jajang-jajang": [
        ("자장", 0),
        ("자장", 2),
        ("우리", 4),
        ("아가", 2),
        ("꼬꼬", 0),
        ("닭아", -1),
        ("우지", 0),
        ("마라", 2),
        ("우리", 4),
        ("아가", 2),
        ("잠을", 0),
        ("깰라", -3),
        ("자장", 0),
        ("자장", 2),
        ("잘도", 0),
        ("잔다", -3),
    ],
    "dalgang-dalgang": [
        ("달강", 0),
        ("달강", 2),
        ("서울", 4),
        ("길은", 2),
        ("밤이", 0),
        ("깊고", -1),
        ("달빛은", 0),
        ("밝다", 2),
        ("우리", 4),
        ("아가", 2),
        ("고운", 0),
        ("꿈을", -1),
        ("꾸며", 0),
        ("새근", -3),
        ("새근", -3),
        ("잠들자", -5),
    ],
    "saeya-saeya": [
        ("새야", 0),
        ("새야", 2),
        ("파랑새야", 4),
        ("녹두밭에", 5),
        ("앉지", 4),
        ("마라", 2),
        ("녹두꽃이", 0),
        ("떨어지면", 2),
        ("청포장수", 4),
        ("울고", 2),
        ("간다", -3),
        ("새야", 0),
        ("새야", 2),
        ("파랑새야", -3),
    ],
}


def render_token(token: str, semitones: int, directory: Path) -> np.ndarray:
    source = directory / f"{len(list(directory.iterdir()))}.aiff"
    subprocess.run(  # noqa: S603
        ["/usr/bin/say", "-v", "Yuna", "-r", "105", "-o", str(source), token],
        check=True,
        timeout=30,
    )
    audio, _ = librosa.load(source, sr=SAMPLE_RATE, mono=True)
    audio, _ = librosa.effects.trim(audio, top_db=28)
    audio = librosa.effects.time_stretch(audio, rate=0.78)
    audio = librosa.effects.pitch_shift(audio, sr=SAMPLE_RATE, n_steps=semitones)
    fade = min(len(audio) // 4, int(SAMPLE_RATE * 0.05))
    if fade:
        envelope = np.ones(len(audio), dtype=np.float32)
        envelope[:fade] = np.linspace(0, 1, fade, dtype=np.float32)
        envelope[-fade:] = np.linspace(1, 0, fade, dtype=np.float32)
        audio *= envelope
    return audio.astype(np.float32)


def main() -> None:
    if platform.system() != "Darwin":
        raise SystemExit("이 재현 스크립트는 macOS의 Yuna 음성을 사용합니다")
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    gap = np.zeros(int(SAMPLE_RATE * 0.12), dtype=np.float32)
    with tempfile.TemporaryDirectory(prefix="dameum-lullaby-build-") as temp:
        temporary = Path(temp)
        for track_id, sequence in TRACKS.items():
            parts = []
            for token, semitones in sequence:
                parts.extend((render_token(token, semitones, temporary), gap))
            audio = np.concatenate(parts)
            peak = float(np.max(np.abs(audio)))
            if peak:
                audio = audio / peak * 0.88
            sf.write(ASSET_DIR / f"{track_id}.wav", audio, SAMPLE_RATE, subtype="PCM_16")


if __name__ == "__main__":
    main()
