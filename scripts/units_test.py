"""Stage 5 real test: cached Gnani transcript -> punctuated, timed units.

Usage:  .venv\\Scripts\\python -m scripts.units_test outputs\\transcripts\\chai_video.json
Cost:   1 Gemini call the first time (punctuation); 0 Gnani calls.
Output: outputs/units/<name>.json + a table
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.config import OUTPUT_DIR
from src.llm import LLM
from src.units import make_units


def main(transcript_path: str) -> None:
    t = json.loads(Path(transcript_path).read_text(encoding="utf-8"))
    llm = LLM()
    units = make_units(t, llm)

    out = OUTPUT_DIR / "units" / Path(transcript_path).name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([u.to_dict() for u in units], ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'id':>2} {'start':>6} {'end':>6} {'slot':>6} {'gap':>5}  ok  text")
    for u in units:
        print(f"{u.id:2d} {u.start:6.2f} {u.end:6.2f} {u.slot:6.2f} {u.gap:5.2f}  "
              f"{'Y' if u.punctuation_ok else 'N'}   {u.text}")
    print(f"\nUnits: {len(units)}   Gemini real calls: {llm.api_calls}   Saved: {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m scripts.units_test <transcript json>")
    main(sys.argv[1])
