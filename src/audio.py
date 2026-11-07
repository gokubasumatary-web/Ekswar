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


def _filter_bytes(data: bytes, audio_filter: str) -> bytes:
    """Run one ffmpeg audio filter on in-memory WAV and return WAV bytes (same rate/channels)."""
    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d) / "in.wav", Path(d) / "out.wav"
        src.write_bytes(data)
        _run([find_tool("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
              "-af", audio_filter, "-c:a", "pcm_s16le", str(dst)])
        return dst.read_bytes()


def change_tempo(data: bytes, tempo: float) -> bytes:
    """Speed speech up (tempo > 1) without changing pitch (ffmpeg atempo)."""
    if not 0.5 <= tempo <= 2.0:
        raise AudioError(f"tempo {tempo} outside the safe 0.5-2.0 range")
    return _filter_bytes(data, f"atempo={tempo:.4f}")


def find_pauses(path: str | Path, noise_db: float = -38.0, min_silence: float = 0.3) -> list[tuple[float, float]]:
    """Quiet stretches (start, end) in seconds, via ffmpeg silencedetect. Use on the VOICE stem."""
    proc = subprocess.run([find_tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-af",
                           f"silencedetect=n={noise_db}dB:d={min_silence}", "-f", "null", "-"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise AudioError(f"ffmpeg silencedetect failed: {proc.stderr.strip()[-400:]}")
    pauses, start = [], None
    for line in proc.stderr.splitlines():
        if "silence_start:" in line:
            start = float(line.split("silence_start:")[1].split()[0])
        elif "silence_end:" in line and start is not None:
            pauses.append((max(start, 0.0), float(line.split("silence_end:")[1].split()[0])))
            start = None
    return pauses


def slice_for_stt(path: str | Path, start: float, end: float) -> bytes:
    """A piece of an audio file as 16 kHz mono WAV bytes (for Gnani REST, <= 30 s)."""
    with tempfile.TemporaryDirectory() as d:
        dst = Path(d) / "slice.wav"
        _run([find_tool("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}",
              "-t", f"{max(end - start, 0.05):.3f}", "-i", str(path), "-ar", "16000", "-ac", "1",
              "-c:a", "pcm_s16le", str(dst)])
        return dst.read_bytes()


def speech_for_stt(data: bytes, speech_seconds: float) -> bytes:
    """Only the spoken part of a clip (padding removed), as 16 kHz mono WAV.

    Why: the QA check should judge the speech, not our padding; and Gnani converts to
    16 kHz mono anyway, so this upload is ~3x smaller. (We first suspected the padding
    caused Gnani's HTTP 504s; later runs showed the 504s are intermittent server-side
    errors on any clip. See NOTES.md.)
    """
    return _filter_bytes_args(data, ["-t", f"{speech_seconds + 0.05:.3f}", "-ar", "16000", "-ac", "1"])


def _filter_bytes_args(data: bytes, args: list[str]) -> bytes:
    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d) / "in.wav", Path(d) / "out.wav"
        src.write_bytes(data)
        _run([find_tool("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), *args,
              "-c:a", "pcm_s16le", str(dst)])
        return dst.read_bytes()


def pad_to(data: bytes, seconds: float) -> bytes:
    """Add silence at the end so the clip lasts at least `seconds`. Never cuts audio."""
    return _filter_bytes(data, f"apad=whole_dur={seconds:.3f}")


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
