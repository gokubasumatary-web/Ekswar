"""Stage 10: the whole Ekswar pipeline, one function.

    run(video, langs, ref) -> RunResult

  1 separate voice / music (Demucs, or --no-music)        local
  2 transcribe Hindi (Gnani Prisma v2.5 batch)            Gnani
  3 units: punctuation + slots (Gemini)                   Gemini
  4 voice embedding (Gnani, cached)                       Gnani
  per language:
  5 translate (Gemini)                                    Gemini
  6 timing agent (Gnani cloned TTS + Gemini shortening)   Gnani + Gemini
  7 quality check (Gnani Prisma REST)                     Gnani
  8 mix -> MP4 + SRT                                      local
  9 report.json                                           local

Every API result is cached, so re-running costs nothing for unchanged inputs.
A failed unit is marked and skipped; key/credit errors (FatalAPIError) stop the run.
The Gnani and Gemini clients are passed in, so tests can use fakes.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .audio import change_tempo, duration, duration_of_bytes, pad_to, speech_for_stt, to_wav
from .config import OUTPUT_DIR, SOURCE_LANGUAGE, SUPPORTED_TARGETS
from .mix import Placed, render
from .qa import QA_THRESHOLD, check_clip
from .retry import FatalAPIError
from .segment import refine_segments
from .separate import extract_audio, prepare_for_stt, separate
from .timing import fit_unit
from .translate import shorten_line, translate_units
from .units import make_units

MAX_VIDEO_SECONDS = 180.0       # scope: videos of 3 minutes or less
REF_MIN, REF_MAX = 5.0, 30.0    # Gnani docs: 5-30 s of clean reference speech
STEPS = 9


class InputError(ValueError):
    """Input outside Ekswar's scope (checked before spending any credits)."""


@dataclass
class LangResult:
    lang: str
    mp4: Path | None = None
    srt: Path | None = None
    units: list[dict] = field(default_factory=list)
    report: dict = field(default_factory=dict)


@dataclass
class RunResult:
    out_dir: Path
    langs: dict[str, LangResult]
    report_path: Path


def check_inputs(video: Path, ref: Path, langs: list[str]) -> tuple[float, float]:
    for p in (video, ref):
        if not p.exists():
            raise InputError(f"file not found: {p}")
    bad = [l for l in langs if l not in SUPPORTED_TARGETS]
    if bad or not langs:
        raise InputError(f"unsupported language(s) {bad}; use {', '.join(SUPPORTED_TARGETS)}")
    v = duration(video)
    if v > MAX_VIDEO_SECONDS:
        raise InputError(f"video is {v:.0f} s; Ekswar handles videos of {MAX_VIDEO_SECONDS / 60:.0f} minutes or less")
    r = duration(ref)
    if not REF_MIN <= r <= REF_MAX:
        raise InputError(f"voice sample is {r:.1f} s; it must be {REF_MIN:.0f}-{REF_MAX:.0f} s of clean speech")
    return v, r


def summarize(lang: str, rows: list[dict], seconds: float, calls: dict) -> dict:
    """Metrics for report.json (pure)."""
    count = {s: sum(r["status"] == s for r in rows) for s in ("fit", "sped_up", "rewritten", "flagged", "failed")}
    sims = [r["qa_similarity"] for r in rows if r.get("qa_similarity") is not None]
    return {
        "language": lang,
        "language_name": SUPPORTED_TARGETS[lang],
        "total_units": len(rows),
        **count,
        "slowed": sum((r.get("tempo") or 1.0) < 1.0 for r in rows),  # short lines stretched (<= 0.9x)
        "qa_flags": sum(bool(r.get("qa_flag")) for r in rows),
        "qa_not_checked": sum(r.get("qa_similarity") is None and r["status"] != "failed" for r in rows),
        "qa_threshold": QA_THRESHOLD,
        "average_similarity": round(sum(sims) / len(sims), 1) if sims else None,
        "processing_seconds": round(seconds, 1),
        **calls,
    }


def run(video: str | Path, langs: list[str], ref: str | Path, *, gnani, llm,
        names: list[str] | None = None, no_music: bool = False, out_root: Path | None = None,
        progress: Callable[[int, int, str], None] | None = None, log: Callable[[str], None] = print) -> RunResult:
    video, ref = Path(video), Path(ref)
    names = names or []
    say = progress or (lambda i, n, msg: log(f"[{i}/{n}] {msg}"))
    t0 = time.time()

    video_secs, ref_secs = check_inputs(video, ref, langs)
    out_dir = (out_root or OUTPUT_DIR / "runs") / video.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. separation
    say(1, STEPS, "Separating voice and music" + (" (skipped: --no-music)" if no_music else " (Demucs)"))
    audio = extract_audio(video, out_dir / "audio.wav")
    stems = separate(audio, no_music=no_music)

    # 2. transcription
    say(2, STEPS, "Transcribing Hindi with Gnani Prisma v2.5")
    stt_wav = prepare_for_stt(stems.vocals, out_dir / "vocals_16k_mono.wav")
    transcript = gnani.transcribe_batch(stt_wav, SOURCE_LANGUAGE, log=log)
    (out_dir / "transcript.json").write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
    # long segments -> split at the speaker's pauses, exact text per piece (Gnani REST, cached)
    transcript, split_stats = refine_segments(
        transcript, stems.vocals,
        lambda wav: gnani.transcribe_rest(wav, SOURCE_LANGUAGE, what="split segment")["transcript"], warn=log)
    if split_stats["split_segments"]:
        log(f"  split {split_stats['split_segments']} long segment(s): "
            f"{split_stats['segments_before']} -> {split_stats['segments_after']} lines")
        (out_dir / "transcript_split.json").write_text(json.dumps(transcript, ensure_ascii=False, indent=2),
                                                       encoding="utf-8")

    # 3. units
    say(3, STEPS, "Building sentence units (Gemini punctuation)")
    units = make_units(transcript, llm, warn=log)
    if not units:
        raise InputError("no speech was found in the video")
    (out_dir / "units.json").write_text(json.dumps([u.to_dict() for u in units], ensure_ascii=False, indent=2),
                                        encoding="utf-8")

    # 4. embedding
    say(4, STEPS, "Creating the voice embedding (Gnani)")
    ref_wav = to_wav(ref, out_dir / "ref_clean.wav", sample_rate=44100, channels=1, trim_leading_silence=True)
    emb = gnani.create_voice_embedding(ref_wav)

    shared_secs = time.time() - t0
    results: dict[str, LangResult] = {}
    for lang in langs:
        lt0 = time.time()
        g0, l0 = gnani.api_calls, llm.api_calls
        ldir = out_dir / lang
        ldir.mkdir(exist_ok=True)

        # 5. translation
        say(5, STEPS, f"{SUPPORTED_TARGETS[lang]}: translating {len(units)} lines (Gemini)")
        trans = translate_units(units, lang, llm, names=names, warn=log)

        # 6. timing agent
        say(6, STEPS, f"{SUPPORTED_TARGETS[lang]}: speaking in your voice + fitting the timing")
        rows, placed = [], []
        for u, t in zip(units, trans):
            row = {"id": u.id, "start": u.start, "end": u.end, "slot": u.slot, "original": u.text,
                   "translation": t.text, "status": "failed", "note": ""}
            if t.error or not t.text:
                row["note"] = f"translation failed: {t.error}"
                rows.append(row)
                continue
            try:
                r = fit_unit(
                    u.id, t.text, u.slot, u.gap,
                    synthesize=lambda text, uid=u.id: gnani.synthesize_cloned(text, emb, what=f"TTS unit {uid} {lang}"),
                    measure=duration_of_bytes,
                    shorten=lambda text, want, src=u.text: shorten_line(llm, lang, src, text, want, names),
                    speed_up=change_tempo, pad=pad_to, log=log)
            except FatalAPIError:
                raise
            except Exception as e:
                row["note"] = f"synthesis failed: {str(e)[:200]}"
                log(f"WARNING: unit {u.id} ({lang}) {row['note']}")
                rows.append(row)
                continue
            (ldir / f"unit_{u.id}.wav").write_bytes(r.audio)
            row.update(status=r.status, final_text=r.text, budget=r.budget, spoken=r.raw_duration,
                       tempo=r.tempo, final_duration=r.final_duration, rewrites=r.rewrites, note=r.note)
            rows.append(row)
            placed.append(Placed(u.id, u.start, r.audio, r.final_duration, r.text))

        # 7. QA
        say(7, STEPS, f"{SUPPORTED_TARGETS[lang]}: quality check (Gnani listens to each line)")
        stt = lambda audio, l: gnani.transcribe_rest(audio, l, what=f"QA {l}")["transcript"]
        by_id = {p.unit_id: p for p in placed}
        for row in rows:
            p = by_id.get(row["id"])
            if p is None:
                continue
            speech = speech_for_stt(p.audio, p.speech)  # no padding silence (it made Gnani time out)
            q = check_clip(stt, p.unit_id, lang, speech, p.text, p.speech)
            row.update(qa_similarity=q.similarity, qa_flag=q.qa_flag, qa_heard=q.heard,
                       qa_note=q.note)

        # 8. mix
        say(8, STEPS, f"{SUPPORTED_TARGETS[lang]}: mixing with the music and writing the video")
        out = render(video, stems.no_vocals, placed, out_dir / f"{video.stem}.{lang}", lang, warn=log)

        calls = {"gnani_api_calls": gnani.api_calls - g0, "gemini_api_calls": llm.api_calls - l0}
        rep = summarize(lang, rows, time.time() - lt0, calls)
        results[lang] = LangResult(lang, out["mp4"], out["srt"], rows, rep)
        (ldir / "units_result.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    # 9. report
    say(9, STEPS, "Writing report.json")
    report = {
        "video": str(video), "video_seconds": round(video_secs, 2), "voice_sample_seconds": round(ref_secs, 2),
        "source_language": SOURCE_LANGUAGE, "music_separated": not no_music,
        "units": len(units), "segment_split": split_stats, "shared_steps_seconds": round(shared_secs, 1),
        "total_processing_seconds": round(time.time() - t0, 1),
        "gnani_api_calls_total": gnani.api_calls, "gemini_api_calls_total": llm.api_calls,
        "gemini_fallback_used": getattr(llm, "fallback_used", 0),
        "gnani_credits_used": "not available via the API; check the Gnani dashboard",
        "label": "AI-dubbed. Voice cloned with the speaker's consent. No lip-sync.",
        "languages": {l: r.report for l, r in results.items()},
    }
    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return RunResult(out_dir, results, report_path)
