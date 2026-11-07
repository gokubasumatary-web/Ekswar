"""Ekswar command line: dub a Hindi video into Tamil, Bengali or Marathi in your own voice.

Examples:
  python cli.py --video samples\\chai_video.mp4 --lang ta-IN --ref samples\\ref_voice_raw.mpeg
  python cli.py --video in.mp4 --lang ta-IN,bn-IN,mr-IN --ref my_voice.mp3 --names "गुथल बसुमतारी (Guthal Basumatary)"
  python cli.py --video talk.mp4 --lang mr-IN --ref my_voice.wav --no-music
"""

from __future__ import annotations

import argparse
import sys

from src.config import SUPPORTED_TARGETS, ConfigError


def main() -> int:
    p = argparse.ArgumentParser(description="Ekswar: one voice, every Indian language.")
    p.add_argument("--video", required=True, help="Hindi video, one speaker, 3 minutes or less")
    p.add_argument("--lang", required=True, help=f"target language(s), comma-separated: {', '.join(SUPPORTED_TARGETS)}")
    p.add_argument("--ref", required=True, help="5-30 s recording of YOUR voice (consent required)")
    p.add_argument("--names", default="", help="comma-separated names to keep, e.g. \"गुथल बसुमतारी (Guthal Basumatary)\"")
    p.add_argument("--no-music", action="store_true", help="skip music separation (video has no background music)")
    a = p.parse_args()

    # imported here so `--help` works even before the environment is set up
    from src.gnani import GnaniClient
    from src.llm import LLM
    from src.pipeline import InputError, run
    from src.retry import FatalAPIError

    langs = [l.strip() for l in a.lang.split(",") if l.strip()]
    names = [n.strip() for n in a.names.split(",") if n.strip()]
    try:
        result = run(a.video, langs, a.ref, gnani=GnaniClient(), llm=LLM(), names=names, no_music=a.no_music)
    except (InputError, ConfigError) as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return 2
    except FatalAPIError as e:
        print(f"\nSTOPPED: {e}", file=sys.stderr)
        return 3

    print("\n" + "=" * 70)
    for lang, r in result.langs.items():
        s = r.report
        print(f"{s['language_name']:8} {r.mp4}")
        print(f"         units {s['total_units']}: fit {s['fit']} (slowed {s['slowed']}), sped_up {s['sped_up']}, "
              f"rewritten {s['rewritten']}, "
              f"flagged {s['flagged']}, failed {s['failed']} | QA avg {s['average_similarity']}% "
              f"({s['qa_flags']} flagged, {s['qa_not_checked']} not checked) | {s['processing_seconds']} s")
    print(f"Report: {result.report_path}")
    print("Label every output as AI-dubbed. No lip-sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
