"""Small ffmpeg/ffprobe helpers shared by all stages."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .config import find_tool


class AudioError(RuntimeError):
    pass


def _run(args: list[str]) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise AudioError(f"{Path(args[0]).name} failed: {proc.stderr.strip()[-800:]}")
    return proc.stdout


def duration(path: str | Path) -> float:
    """Length of an audio/video file in seconds."""
    out = _run([find_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def duration_of_bytes(data: bytes, suffix: str = ".wav") -> float:
    """Length of in-memory audio (e.g. a TTS response) in seconds."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / f"clip{suffix}"
        p.write_bytes(data)
        return duration(p)


def to_wav(src: str | Path, dst: str | Path, *, sample_rate: int, channels: int = 1,
           trim_leading_silence: bool = False) -> Path:
    """Convert any audio/video file to 16-bit PCM WAV.

    trim_leading_silence: remove quiet audio (below -40 dB) at the very start.
    """
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    args = [find_tool("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-vn"]
    if trim_leading_silence:
        args += ["-af", "silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.1"]
    args += ["-ar", str(sample_rate), "-ac", str(channels), "-c:a", "pcm_s16le", str(dst)]
    _run(args)
    return dst
