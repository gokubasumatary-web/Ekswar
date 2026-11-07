"""Stage 7 real test: translations -> cloned voice -> Timing Agent -> timing table.

Usage:
  .venv\\Scripts\\python -m scripts.timing_test outputs\\units\\chai_video.json --lang ta-IN \\
        --ref samples\\ref_voice_raw.mpeg [--names "..."] [--units 1]

Cost (first run only; everything is cached):
  Gnani: 1 TTS call per unit, +1 per rewrite.   Gemini: 1 call per rewrite.
Output: outputs/timing/<name>.<lang>/unit_<id>.wav + timing.json + a table
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.audio import change_tempo, duration_of_bytes, pad_to, to_wav
from src.config import OUTPUT_DIR
from src.gnani import GnaniClient
from src.llm import LLM
from src.timing import fit_unit
from src.translate import shorten_line
from src.units import Unit


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("units_json")
    p.add_argument("--lang", required=True)
    p.add_argument("--ref", required=True, help="voice reference recording (5-30 s)")
    p.add_argument("--names", default="")
    p.add_argument("--units", default="", help="comma-separated unit ids to run (default: all)")
    p.add_argument("--squeeze", type=float, default=1.0,
                   help="STRESS TEST ONLY: multiply slots and gaps by this (e.g. 0.5) to force speed-ups/rewrites")
    a = p.parse_args()

    stem = Path(a.units_json).stem
    units = [Unit(**d) for d in json.loads(Path(a.units_json).read_text(encoding="utf-8"))]
    tr_path = OUTPUT_DIR / "translations" / f"{stem}.{a.lang}.json"
    trans = {d["id"]: d for d in json.loads(tr_path.read_text(encoding="utf-8"))}
    names = [n.strip() for n in a.names.split(",") if n.strip()]
    only = {int(x) for x in a.units.split(",") if x.strip()}

    gnani, llm = GnaniClient(), LLM()
    ref = to_wav(a.ref, OUTPUT_DIR / "voice_test" / "ref_clean.wav", sample_rate=44100, channels=1,
                 trim_leading_silence=True)
    emb = gnani.create_voice_embedding(ref)  # cached since Stage 1

    if a.squeeze != 1.0:
        for u in units:
            u.slot, u.gap = round(u.slot * a.squeeze, 3), round(u.gap * a.squeeze, 3)
        print(f"*** STRESS TEST: slots and gaps x{a.squeeze} (not real timings) ***")
    suffix = "" if a.squeeze == 1.0 else f".squeeze{a.squeeze}"
    out_dir = OUTPUT_DIR / "timing" / f"{stem}.{a.lang}{suffix}"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for u in units:
        if only and u.id not in only:
            continue
        t = trans[u.id]
        if t.get("error") or not t["text"]:
            print(f"unit {u.id}: skipped (no translation: {t.get('error')})")
            continue
        try:
            r = fit_unit(
                u.id, t["text"], u.slot, u.gap,
                synthesize=lambda text, uid=u.id: gnani.synthesize_cloned(text, emb, what=f"TTS unit {uid} {a.lang}"),
                measure=duration_of_bytes,
                shorten=lambda text, want, src=u.text: shorten_line(llm, a.lang, src, text, want, names),
                speed_up=change_tempo,
                pad=pad_to,
            )
        except Exception as e:  # one failed unit must not stop the others
            print(f"unit {u.id}: FAILED ({e})")
            results.append({"unit_id": u.id, "status": "failed", "note": str(e)[:300]})
            continue
        (out_dir / f"unit_{u.id}.wav").write_bytes(r.audio)
        results.append(r.to_dict())

    (out_dir / "timing.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'unit':>4} {'slot':>6} {'budget':>6} {'spoken':>6} {'tempo':>5} {'final':>6} {'rw':>2}  status")
    for r in results:
        if r["status"] == "failed":
            print(f"{r['unit_id']:4d}  FAILED  {r['note'][:80]}")
            continue
        u = next(x for x in units if x.id == r["unit_id"])
        print(f"{r['unit_id']:4d} {u.slot:6.2f} {r['budget']:6.2f} {r['raw_duration']:6.2f} {r['tempo']:5.2f} "
              f"{r['final_duration']:6.2f} {r['rewrites']:2d}  {r['status']}  {r['note']}")
    print(f"\nGnani real calls: {gnani.api_calls}   Gemini real calls: {llm.api_calls}   Output: {out_dir}")


if __name__ == "__main__":
    main()
