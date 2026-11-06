"""Stage 2: get the audio out of a video and split it into voice + music.

  extract_audio(video)        -> audio.wav        (ffmpeg)
  separate(audio)             -> vocals.wav, no_vocals.wav   (Demucs, local, CPU)
  separate(audio, no_music=True) -> vocals = original audio, no_vocals = silence
  prepare_for_stt(vocals)     -> 16 kHz mono WAV under 10 MB (Gnani batch limit)

Demucs results are cached by the audio file's fingerprint, so a video is only
separated once. Run directly:  python -m src.separate <video> [--no-music]
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .audio import AudioError, _run, duration, to_wav
from .cache import file_hash
from .config import CACHE_DIR, find_tool

WORK_RATE = 44100          # internal sample rate for everything we mix
DEMUCS_MODEL = "htdemucs"  # Demucs default model
STT_RATE = 16000
STT_MAX_BYTES = 10 * 1024 * 1024  # Gnani batch direct-upload limit (docs)


@dataclass
class Stems:
    vocals: Path
    no_vocals: Path
    separated: bool  # False when --no-music was used


def extract_audio(video: str | Path, dst: str | Path) -> Path:
    """Video -> stereo 44.1 kHz WAV (keeps music stereo for the final mix)."""
    return to_wav(video, dst, sample_rate=WORK_RATE, channels=2)


def separate(audio: str | Path, *, no_music: bool = False, device: str = "cpu") -> Stems:
    audio = Path(audio)
    out_dir = CACHE_DIR / "separation" / (file_hash(audio) + ("-nomusic" if no_music else ""))
    vocals, no_vocals = out_dir / "vocals.wav", out_dir / "no_vocals.wav"
    if vocals.exists() and no_vocals.exists():
        return Stems(vocals, no_vocals, separated=not no_music)

    out_dir.mkdir(parents=True, exist_ok=True)
    if no_music:
        shutil.copyfile(audio, vocals)
        _silence_like(audio, no_vocals)
        return Stems(vocals, no_vocals, separated=False)

    with tempfile.TemporaryDirectory() as tmp:
        cmd = [sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", DEMUCS_MODEL,
               "-d", device, "-o", tmp, str(audio)]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            raise AudioError(f"Demucs failed: {proc.stderr.strip()[-800:]}")
        produced = Path(tmp) / DEMUCS_MODEL / audio.stem
        # move into the cache only after BOTH files exist (no half results cached)
        for name in ("vocals.wav", "no_vocals.wav"):
            if not (produced / name).exists():
                raise AudioError(f"Demucs did not produce {name}")
        shutil.move(produced / "no_vocals.wav", no_vocals)
        shutil.move(produced / "vocals.wav", vocals)
    return Stems(vocals, no_vocals, separated=True)


def prepare_for_stt(vocals: str | Path, dst: str | Path) -> Path:
    """16 kHz mono WAV for Gnani Prisma batch. Fails clearly if over 10 MB."""
    dst = to_wav(vocals, dst, sample_rate=STT_RATE, channels=1)
    size = dst.stat().st_size
    if size > STT_MAX_BYTES:
        raise AudioError(f"STT upload is {size / 1e6:.1f} MB; Gnani direct upload max is 10 MB "
                         f"(about 5 min of 16 kHz mono). Use a shorter video.")
    return dst


def _silence_like(ref: Path, dst: Path) -> None:
    """Write stereo silence with the same length as `ref`."""
    secs = duration(ref)
    _run([find_tool("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error",
          "-f", "lavfi", "-i", f"anullsrc=r={WORK_RATE}:cl=stereo", "-t", f"{secs:.3f}",
          "-c:a", "pcm_s16le", str(dst)])


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Extract + separate audio from a video")
    p.add_argument("video")
    p.add_argument("--no-music", action="store_true")
    a = p.parse_args()
    from .config import OUTPUT_DIR
    out = OUTPUT_DIR / "separation" / Path(a.video).stem
    audio = extract_audio(a.video, out / "audio.wav")
    stems = separate(audio, no_music=a.no_music)
    stt = prepare_for_stt(stems.vocals, out / "vocals_16k_mono.wav")
    for label, path in [("audio", audio), ("vocals", stems.vocals),
                        ("no_vocals", stems.no_vocals), ("stt upload", stt)]:
        print(f"{label:11} {duration(path):6.2f} s  {path.stat().st_size / 1e6:5.2f} MB  {path}")
