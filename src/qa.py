"""Stage 8: quality check of dubbed clips.

Gnani Prisma (REST, target language) transcribes each final clip; we compare
what it heard with the text we intended (character-level similarity, rapidfuzz).

This is a WARNING LIGHT, not a verdict: STT spelling/formatting differs from
our text, so a correct clip rarely scores 100%. Below QA_THRESHOLD -> qa_flag.
Clips over 30 s are not checked (REST limit in the docs).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from rapidfuzz import fuzz

from .units import words_only

REST_MAX_SECONDS = 30.0
# Set from real scores (2026-11-07, chai video): correct clips 93.7-98.3 %,
# wrong-line clips 36.7-47.5 %. 80 sits in the gap with margin, and also
# catches partly garbled clips. Small sample: revisit on the 2-3 min video.
QA_THRESHOLD = 80.0


@dataclass
class QAResult:
    unit_id: int
    lang: str
    checked: bool
    intended: str
    heard: str
    similarity: float | None
    qa_flag: bool
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def normalize(text: str) -> str:
    """Lower-case, no punctuation/symbols, single spaces. Keeps every letter and vowel sign."""
    return words_only(text).lower()


def similarity(intended: str, heard: str) -> float:
    a, b = normalize(intended), normalize(heard)
    if not a and not b:
        return 100.0
    return round(fuzz.ratio(a, b), 1)


def judge(unit_id: int, lang: str, intended: str, heard: str,
          threshold: float = QA_THRESHOLD) -> QAResult:
    sim = similarity(intended, heard)
    note = "no speech heard" if not heard.strip() else ""
    return QAResult(unit_id, lang, True, intended, heard, sim, sim < threshold, note)


def check_clip(stt, unit_id: int, lang: str, audio: bytes, intended: str, duration: float,
               threshold: float = QA_THRESHOLD) -> QAResult:
    """`stt(audio, lang) -> transcript str`. Never raises: failures become 'not checked'."""
    if duration > REST_MAX_SECONDS:
        return QAResult(unit_id, lang, False, intended, "", None, False,
                        f"not checked: {duration:.1f} s > {REST_MAX_SECONDS:.0f} s REST limit")
    try:
        heard = stt(audio, lang)
    except Exception as e:  # QA must never stop the run
        return QAResult(unit_id, lang, False, intended, "", None, False, f"not checked: {str(e)[:200]}")
    return judge(unit_id, lang, intended, heard, threshold)
