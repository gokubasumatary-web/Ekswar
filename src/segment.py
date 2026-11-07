"""Split long Gnani segments at natural pauses (better timing sync).

Why (2026-11-07, 2-min demo): Gnani batch returned segments up to 31 s long. Inside one
long segment the dub drifts: the cloned voice finishes early, then stays silent while the
speaker's mouth still moves. Shorter lines start exactly where the speaker starts each part.

How:
  1. ffmpeg silencedetect on the VOICE stem -> pauses (free, local)
  2. cut_points(): cut long segments at pause midpoints into ~MIN_LEN..MAX_LEN chunks (pure)
  3. each chunk -> Gnani Prisma REST (hi-IN) -> exact text for that chunk (cached)
  4. any chunk fails or comes back empty -> keep the ORIGINAL segment (never lose text)

This is timing sync, not lip-sync: the video's mouth movements are never changed.
"""

from __future__ import annotations

from typing import Callable

from .audio import find_pauses, slice_for_stt

MAX_LEN = 8.0   # segments longer than this get split
MIN_LEN = 3.0   # no chunk shorter than this (tiny fragments translate badly)


def cut_points(start: float, end: float, pauses: list[tuple[float, float]],
               max_len: float = MAX_LEN, min_len: float = MIN_LEN) -> list[tuple[float, float]]:
    """Split [start, end] at pause midpoints into chunks of about min_len..max_len seconds."""
    if end - start <= max_len:
        return [(start, end)]
    mids = sorted((a + b) / 2 for a, b in pauses if start < (a + b) / 2 < end)
    chunks, cur = [], start
    while True:
        ok = [m for m in mids if m - cur >= min_len and end - m >= min_len]
        if end - cur <= max_len or not ok:
            break
        within = [m for m in ok if m - cur <= max_len]
        cut = within[-1] if within else ok[0]   # longest chunk that fits, else the next pause
        chunks.append((cur, cut))
        cur = cut
    chunks.append((cur, end))
    return [(round(a, 3), round(b, 3)) for a, b in chunks]


def refine_segments(transcript: dict, vocals_path, stt: Callable[[bytes], str], *,
                    pauses: list[tuple[float, float]] | None = None, warn=print) -> tuple[dict, dict]:
    """Return (transcript with long segments split, stats). `stt(wav_bytes) -> Hindi text`."""
    segs = transcript.get("segments") or []
    if not any((s["end_time"] - s["start_time"]) > MAX_LEN for s in segs):
        return transcript, {"split_segments": 0, "new_segments": 0, "kept_unsplit": 0}
    pauses = find_pauses(vocals_path) if pauses is None else pauses
    out, split, kept = [], 0, 0
    for s in segs:
        chunks = cut_points(s["start_time"], s["end_time"], pauses)
        if len(chunks) == 1:
            out.append(s)
            continue
        try:
            texts = [stt(slice_for_stt(vocals_path, a, b)).strip() for a, b in chunks]
        except Exception as e:  # keep the original segment rather than lose text
            warn(f"WARNING: could not split segment at {s['start_time']:.1f}s ({str(e)[:100]}); kept as one line")
            out.append(s)
            kept += 1
            continue
        if not all(texts):
            warn(f"WARNING: a chunk of the segment at {s['start_time']:.1f}s had no speech; kept as one line")
            out.append(s)
            kept += 1
            continue
        split += 1
        out.extend({**s, "start_time": a, "end_time": b, "text": t, "split_from": s["start_time"]}
                   for (a, b), t in zip(chunks, texts))
    stats = {"split_segments": split, "new_segments": len(out) - len(segs) + split, "kept_unsplit": kept,
             "segments_before": len(segs), "segments_after": len(out)}
    return {**transcript, "segments": out}, stats
