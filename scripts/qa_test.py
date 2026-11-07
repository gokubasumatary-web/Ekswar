"""Stage 8 real test: Gnani REST STT on each final dubbed clip -> similarity table.

Usage:  .venv\\Scripts\\python -m scripts.qa_test chai_video [--langs ta-IN,bn-IN,mr-IN]
Reads:  outputs/timing/<name>.<lang>/timing.json + unit_<id>.wav   (from Stage 7)
Cost:   1 Gnani REST STT call per clip, first time only (cached).
"""

from __future__ import annotations

import argparse
import json

from src.audio import duration_of_bytes
from src.config import OUTPUT_DIR
from src.gnani import GnaniClient
from src.qa import QA_THRESHOLD, check_clip


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("name")
    p.add_argument("--langs", default="ta-IN,bn-IN,mr-IN")
    a = p.parse_args()

    gnani = GnaniClient()
    stt = lambda audio, lang: gnani.transcribe_rest(audio, lang, what=f"QA {lang}")["transcript"]
    for lang in a.langs.split(","):
        d = OUTPUT_DIR / "timing" / f"{a.name}.{lang}"
        results = []
        for r in json.loads((d / "timing.json").read_text(encoding="utf-8")):
            if r["status"] == "failed":
                continue
            audio = (d / f"unit_{r['unit_id']}.wav").read_bytes()
            results.append(check_clip(stt, r["unit_id"], lang, audio, r["text"], duration_of_bytes(audio)))
        (d / "qa.json").write_text(json.dumps([q.to_dict() for q in results], ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        print(f"\n=== {lang} ===")
        for q in results:
            sim = "  n/a" if q.similarity is None else f"{q.similarity:5.1f}"
            print(f"unit {q.unit_id}  similarity {sim}%  {'FLAG' if q.qa_flag else 'ok  '}  {q.note}")
            print(f"   intended: {q.intended}")
            print(f"   heard:    {q.heard}")
    print(f"\nThreshold {QA_THRESHOLD}%   Gnani real calls: {gnani.api_calls}")


if __name__ == "__main__":
    main()
