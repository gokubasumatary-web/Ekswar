"""Stage 3 real test: video -> separated voice -> Gnani Prisma batch -> Hindi transcript.

Usage:  .venv\\Scripts\\python -m scripts.transcribe_test samples\\chai_video.mp4 [--no-music]
Cost:   1 batch STT job the first time; re-runs are free (cached).
Output: outputs/transcripts/<video>.json (raw, exactly as Gnani returned it)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import OUTPUT_DIR
from src.gnani import GnaniClient
from src.separate import extract_audio, prepare_for_stt, separate


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("--no-music", action="store_true")
    a = p.parse_args()

    name = Path(a.video).stem
    work = OUTPUT_DIR / "separation" / name
    audio = extract_audio(a.video, work / "audio.wav")
    stems = separate(audio, no_music=a.no_music)
    stt_wav = prepare_for_stt(stems.vocals, work / "vocals_16k_mono.wav")

    client = GnaniClient()
    print("Transcribing with Prisma v2.5 batch (hi-IN)...")
    t = client.transcribe_batch(stt_wav, "hi-IN")

    out = OUTPUT_DIR / "transcripts" / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nTop-level keys: {sorted(t.keys())}")
    segs = t.get("segments") or []
    print(f"Segments: {len(segs)}")
    print(f"\n{'#':>2} {'start':>6} {'end':>6} {'len':>5}  text")
    for i, s in enumerate(segs):
        st, en = s.get("start_time"), s.get("end_time")
        print(f"{i:2d} {st:6.2f} {en:6.2f} {en - st:5.2f}  {s.get('text')}")
    print(f"\nfull_transcript: {t.get('full_transcript')}")
    print(f"\nSaved raw JSON: {out}")
    print(f"Real Gnani API calls this run: {client.api_calls}")


if __name__ == "__main__":
    main()
