"""Stage 9 real test: final dubbed MP4 + SRT for each language. No API calls.

Usage:  .venv\\Scripts\\python -m scripts.mix_test samples\\chai_video.mp4 [--langs ta-IN,bn-IN,mr-IN] [--no-music]
Reads:  outputs/units/<name>.json, outputs/timing/<name>.<lang>/ (Stage 7), Demucs stems (cached, Stage 2)
Output: outputs/final/<name>.<lang>.mp4 / .srt
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import OUTPUT_DIR
from src.mix import Placed, render
from src.separate import extract_audio, separate


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("video")
    p.add_argument("--langs", default="ta-IN,bn-IN,mr-IN")
    p.add_argument("--no-music", action="store_true")
    a = p.parse_args()

    name = Path(a.video).stem
    units = {u["id"]: u for u in json.loads((OUTPUT_DIR / "units" / f"{name}.json").read_text(encoding="utf-8"))}
    audio = extract_audio(a.video, OUTPUT_DIR / "separation" / name / "audio.wav")
    music = separate(audio, no_music=a.no_music).no_vocals  # cached since Stage 2

    for lang in a.langs.split(","):
        tdir = OUTPUT_DIR / "timing" / f"{name}.{lang}"
        clips = []
        for r in json.loads((tdir / "timing.json").read_text(encoding="utf-8")):
            if r["status"] == "failed":
                print(f"  unit {r['unit_id']}: failed in timing, left silent")
                continue
            clips.append(Placed(r["unit_id"], units[r["unit_id"]]["start"],
                                (tdir / f"unit_{r['unit_id']}.wav").read_bytes(), r["final_duration"], r["text"]))
        out = render(a.video, music, clips, OUTPUT_DIR / "final" / f"{name}.{lang}", lang)
        print(f"{lang}: {out['mp4']}  ({out['mp4_seconds']:.2f} s; video {out['video_seconds']:.2f} s)  + {out['srt'].name}")


if __name__ == "__main__":
    main()
