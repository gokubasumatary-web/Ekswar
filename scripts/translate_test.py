"""Stage 6 real test: units -> Tamil, Bengali, Marathi translations.

Usage:  .venv\\Scripts\\python -m scripts.translate_test outputs\\units\\chai_video.json [--names "name1,name2"]
Cost:   1 Gemini call per unit per language, the first time only (cached).
Output: outputs/translations/<name>.<lang>.json + a table per language
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import OUTPUT_DIR
from src.llm import LLM
from src.translate import LANGUAGES, translate_units
from src.units import Unit


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("units_json")
    p.add_argument("--names", default="", help="comma-separated names to keep, e.g. 'गोकुल'")
    p.add_argument("--langs", default="ta-IN,bn-IN,mr-IN")
    p.add_argument("--units", default="", help="only re-translate these unit ids (others kept from the saved file)")
    a = p.parse_args()

    all_units = [Unit(**d) for d in json.loads(Path(a.units_json).read_text(encoding="utf-8"))]
    only = {int(x) for x in a.units.split(",") if x.strip()}
    units = [u for u in all_units if not only or u.id in only]
    names = [n.strip() for n in a.names.split(",") if n.strip()]
    llm = LLM()
    stem = Path(a.units_json).stem
    out_dir = OUTPUT_DIR / "translations"
    out_dir.mkdir(parents=True, exist_ok=True)

    for lang in a.langs.split(","):
        results = translate_units(units, lang, llm, names=names, context_units=all_units)
        path = out_dir / f"{stem}.{lang}.json"
        merged = {d["id"]: d for d in json.loads(path.read_text(encoding="utf-8"))} if (only and path.exists()) else {}
        merged.update({r.id: r.to_dict() for r in results})
        path.write_text(json.dumps([merged[k] for k in sorted(merged)], ensure_ascii=False, indent=2),
                        encoding="utf-8")
        print(f"\n=== {LANGUAGES[lang][0]} ({lang}) ===")
        for u, r in zip(units, results):
            flags = [f for f, on in (("OVER", r.over_budget), ("DIGITS", r.digits_found),
                                     ("SCRIPT", not r.script_ok), ("ERROR", bool(r.error))) if on]
            print(f"unit {r.id}  slot {u.slot:5.2f}s  hindi {len(u.text):3d} ch  ->  {r.chars:3d}/{r.budget_chars} ch"
                  f"  script {r.script_ratio:.0%}  {' '.join(flags) or 'ok'}")
            print(f"   {r.text or r.error}")

    print(f"\nGemini real calls: {llm.api_calls}  (backup model used {llm.fallback_used}x)")


if __name__ == "__main__":
    main()
