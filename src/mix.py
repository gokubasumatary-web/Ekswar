"""Stage 9: build the final dubbed video + subtitles.

  build_dub_track()  place each final clip at its unit's start time on a silent track (numpy)
  mix_with_music()   dub track + no_vocals.wav (original music), then loudness-normalise (ffmpeg loudnorm)
  mux_video()        original video stream COPIED (no re-encode) + new audio, tagged "AI-dubbed"
  write_srt()        translated text split into sentences, timed to when the voice speaks them
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from .audio import _run, duration
from .config import find_tool

RATE = 44100
LOUDNESS_TARGET = "I=-16:TP=-1.5:LRA=11"  # common web/streaming loudness
AI_LABEL = "AI-dubbed with Ekswar (voice cloned with consent; timing adjusted by an agent)"
# MP4 stores ISO 639-2 (3-letter) language codes; 2-letter codes are silently dropped.
ISO639_2 = {"ta": "tam", "bn": "ben", "mr": "mar", "hi": "hin"}


@dataclass
class Placed:
    unit_id: int
    start: float     # seconds in the video where this line starts
    audio: bytes     # final WAV from the timing agent
    speech: float    # seconds of actual speech in the clip (before padding)
    text: str        # final spoken text (for subtitles)


# --------------------------------------------------------------------------
# Audio
# --------------------------------------------------------------------------

def _read_mono(wav: bytes) -> np.ndarray:
    data, rate = sf.read(io.BytesIO(wav), dtype="float32", always_2d=True)
    if rate != RATE:
        raise ValueError(f"clip is {rate} Hz, expected {RATE} Hz")
    return data.mean(axis=1)


def build_dub_track(clips: list[Placed], total_seconds: float, *, warn=print) -> np.ndarray:
    """Stereo float32 array (n, 2): every clip added at its start time. Overlaps are summed + warned."""
    n = int(round(total_seconds * RATE))
    track = np.zeros(n, dtype=np.float32)
    busy_until = 0.0
    for c in sorted(clips, key=lambda c: c.start):
        if c.start < busy_until - 0.01:
            warn(f"WARNING: unit {c.unit_id} starts at {c.start:.2f}s but the previous clip runs "
                 f"until {busy_until:.2f}s (overlap)")
        mono = _read_mono(c.audio)
        i = int(round(c.start * RATE))
        if i >= n:
            warn(f"WARNING: unit {c.unit_id} starts after the end of the video; skipped")
            continue
        j = min(i + len(mono), n)
        if i + len(mono) > n:
            warn(f"WARNING: unit {c.unit_id} runs past the end of the video by "
                 f"{(i + len(mono) - n) / RATE:.2f}s; the tail is cut")
        track[i:j] += mono[: j - i]
        busy_until = max(busy_until, c.start + c.speech)
    return np.stack([track, track], axis=1)


def read_stereo(path: str | Path, total_seconds: float) -> np.ndarray:
    """Read a WAV as stereo float32, padded with silence / trimmed to total_seconds."""
    data, rate = sf.read(str(path), dtype="float32", always_2d=True)
    if rate != RATE:
        raise ValueError(f"{path} is {rate} Hz, expected {RATE} Hz")
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    n = int(round(total_seconds * RATE))
    out = np.zeros((n, 2), dtype=np.float32)
    m = min(n, len(data))
    out[:m] = data[:m, :2]
    return out


def mix_with_music(dub: np.ndarray, music: np.ndarray, dst: str | Path) -> Path:
    """Sum dub + music (float, no clipping), then ffmpeg loudnorm to LOUDNESS_TARGET -> 16-bit WAV."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    raw = dst.with_suffix(".premix.wav")
    sf.write(str(raw), dub + music, RATE, subtype="FLOAT")
    _run([find_tool("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
          "-af", f"loudnorm={LOUDNESS_TARGET}", "-ar", str(RATE), "-c:a", "pcm_s16le", str(dst)])
    raw.unlink(missing_ok=True)
    return dst


def mux_video(video: str | Path, audio: str | Path, dst: str | Path, lang: str) -> Path:
    """Copy the original video stream untouched, replace the audio, label it AI-dubbed."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    _run([find_tool("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error",
          "-i", str(video), "-i", str(audio),
          "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
          "-metadata", f"comment={AI_LABEL}",
          "-metadata:s:a:0", f"language={ISO639_2.get(lang.split('-')[0], 'und')}",
          "-metadata:s:a:0", "title=AI-dubbed", str(dst)])
    return dst


# --------------------------------------------------------------------------
# Subtitles
# --------------------------------------------------------------------------

SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in SENTENCE_END.split(text.strip()) if p.strip()]
    return parts or [text.strip()]


def srt_time(seconds: float) -> str:
    ms = int(round(max(seconds, 0) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def subtitle_cues(clips: list[Placed]) -> list[tuple[float, float, str]]:
    """One cue per sentence, timed by its share of characters within the actual speech time."""
    cues = []
    for c in sorted(clips, key=lambda c: c.start):
        sents = split_sentences(c.text)
        total = sum(len(s) for s in sents) or 1
        t = c.start
        for s in sents:
            dur = c.speech * len(s) / total
            cues.append((t, t + dur, s))
            t += dur
    return cues


def write_srt(clips: list[Placed], dst: str | Path) -> Path:
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    blocks = [f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{text}\n"
              for i, (a, b, text) in enumerate(subtitle_cues(clips), start=1)]
    dst.write_text("\n".join(blocks), encoding="utf-8")
    return dst


# --------------------------------------------------------------------------
# Whole stage
# --------------------------------------------------------------------------

def render(video: str | Path, music_wav: str | Path, clips: list[Placed], out_base: str | Path,
           lang: str, *, warn=print) -> dict:
    """Dub track + music -> normalised audio -> MP4 (+ .srt). Returns output paths and lengths."""
    out_base = Path(out_base)
    # NOT with_suffix(): it would treat ".ta-IN" in "video.ta-IN" as an extension and replace it.
    def named(ext: str) -> Path:
        return out_base.parent / f"{out_base.name}{ext}"

    total = duration(video)  # cover the WHOLE video (phone audio can be shorter than the picture)
    dub = build_dub_track(clips, total, warn=warn)
    music = read_stereo(music_wav, total)
    mixed = mix_with_music(dub, music, named(".mix.wav"))
    mp4 = mux_video(video, mixed, named(".mp4"), lang)
    srt = write_srt(clips, named(".srt"))
    return {"mp4": mp4, "srt": srt, "mix": mixed, "video_seconds": total, "mp4_seconds": duration(mp4)}
