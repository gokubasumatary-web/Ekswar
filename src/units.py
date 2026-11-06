"""Stage 5: Gnani transcript -> clean, timed "units" (one unit = one dubbed line).

Design (team decision, option A): each Gnani segment becomes one unit; tiny
segments are merged into a neighbour. Gemini only ADDS punctuation; it must
not change the words (checked; on failure we keep the original words).

Each unit:
    id, start, end, slot (= end - start), gap (silence until the next unit,
    or until the end of the audio for the last one), text_raw, text
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass

from rapidfuzz import fuzz

MIN_UNIT_SECONDS = 1.0       # shorter segments get merged into a neighbour
WORDS_SAME_THRESHOLD = 95.0  # % similarity required between raw and punctuated words


@dataclass
class Unit:
    id: int
    start: float
    end: float
    slot: float
    gap: float
    text_raw: str
    text: str
    punctuation_ok: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------
# Pure functions (no network)
# --------------------------------------------------------------------------

def segments_from_transcript(t: dict, *, warn=print) -> list[dict]:
    """Return [{start, end, text}] from a Gnani batch transcript, in time order."""
    segs = []
    for s in t.get("segments") or []:
        text = (s.get("text") or "").strip()
        if text and s.get("start_time") is not None and s.get("end_time") is not None:
            segs.append({"start": float(s["start_time"]), "end": float(s["end_time"]), "text": text})
    if segs:
        return sorted(segs, key=lambda s: s["start"])
    full = (t.get("full_transcript") or "").strip()
    if not full:
        return []
    warn("WARNING: transcript has no segments; using full_transcript as ONE unit (timing will be coarse)")
    return [{"start": 0.0, "end": float(t.get("duration_seconds") or 0.0), "text": full}]


def merge_tiny(segs: list[dict], min_seconds: float = MIN_UNIT_SECONDS) -> list[dict]:
    """Merge segments shorter than `min_seconds` into the nearer neighbour."""
    segs = [dict(s) for s in segs]
    i = 0
    while len(segs) > 1 and i < len(segs):
        s = segs[i]
        if s["end"] - s["start"] >= min_seconds:
            i += 1
            continue
        gap_before = s["start"] - segs[i - 1]["end"] if i > 0 else float("inf")
        gap_after = segs[i + 1]["start"] - s["end"] if i + 1 < len(segs) else float("inf")
        j = i - 1 if gap_before <= gap_after else i + 1  # neighbour to merge with
        a, b = sorted((i, j))
        segs[a] = {"start": segs[a]["start"], "end": segs[b]["end"],
                   "text": f"{segs[a]['text']} {segs[b]['text']}"}
        del segs[b]
        i = max(a - 1, 0)  # re-check around the merge
    return segs


def build_units(segs: list[dict], total_duration: float) -> list[Unit]:
    """Attach slot and gap to each segment."""
    units = []
    for k, s in enumerate(segs):
        nxt = segs[k + 1]["start"] if k + 1 < len(segs) else max(total_duration, s["end"])
        units.append(Unit(id=k, start=round(s["start"], 3), end=round(s["end"], 3),
                          slot=round(s["end"] - s["start"], 3), gap=round(max(nxt - s["end"], 0.0), 3),
                          text_raw=s["text"], text=s["text"]))
    return units


def words_only(text: str) -> str:
    """Remove punctuation/symbols only (Unicode categories P* and S*), keep every letter
    and vowel sign. (Regex \\w would wrongly drop Devanagari vowel signs like ि े ं.)"""
    text = "".join(" " if unicodedata.category(ch)[0] in "PS" else ch for ch in text)
    return " ".join(text.split())


def same_words(raw: str, punctuated: str) -> float:
    return fuzz.ratio(words_only(raw), words_only(punctuated))


# --------------------------------------------------------------------------
# Gemini step: add punctuation only
# --------------------------------------------------------------------------

PUNCT_SCHEMA = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {"type": "string"}}},
    "required": ["lines"],
}

PUNCT_PROMPT = """You are given {n} lines of an automatic Hindi speech transcript (spoken Hinglish; English words may be written in Devanagari). The transcript has no punctuation.

Task: add punctuation (। , ? !) to each line so it reads as proper sentences.
Rules:
- Return exactly {n} lines, in the same order, one output line per input line.
- Do NOT add, remove, translate, correct or reorder any words. Only add punctuation marks.
- Keep the original script (do not convert Devanagari to Latin or back).

Return JSON: {{"lines": ["...", ...]}}

Lines:
{lines}"""


def punctuate(units: list[Unit], llm, *, warn=print) -> list[Unit]:
    """Ask Gemini for punctuation in ONE call; keep original words if it changed them."""
    if not units:
        return units
    numbered = "\n".join(f"{u.id + 1}. {u.text_raw}" for u in units)
    prompt = PUNCT_PROMPT.format(n=len(units), lines=numbered)
    try:
        lines = llm.ask_json(prompt, PUNCT_SCHEMA, what="punctuation")["lines"]
    except Exception as e:  # LLM failure must not kill the run: fall back to raw text
        warn(f"WARNING: punctuation step failed ({e}); using unpunctuated text")
        for u in units:
            u.punctuation_ok = False
        return units
    if len(lines) != len(units):
        warn(f"WARNING: Gemini returned {len(lines)} lines for {len(units)} units; using unpunctuated text")
        for u in units:
            u.punctuation_ok = False
        return units
    for u, line in zip(units, lines):
        line = re.sub(r"^\s*\d+\.\s*", "", line).strip()  # drop "1. " if echoed back
        score = same_words(u.text_raw, line)
        if score >= WORDS_SAME_THRESHOLD:
            u.text = line
        else:
            u.punctuation_ok = False
            warn(f"WARNING: unit {u.id}: Gemini changed the words (similarity {score:.0f}%); keeping original")
    return units


def make_units(transcript: dict, llm=None, *, warn=print) -> list[Unit]:
    """Full Stage 5: segments -> merge tiny -> units with slot/gap -> punctuation."""
    total = float(transcript.get("duration_seconds") or 0.0)
    units = build_units(merge_tiny(segments_from_transcript(transcript, warn=warn)), total)
    return punctuate(units, llm, warn=warn) if llm is not None else units
