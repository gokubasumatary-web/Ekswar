"""Stage 7: the Timing Agent, which makes every dubbed line fit its original time slot.

Translated lines rarely take the same time to say as the Hindi original. For each unit:

    budget = slot + GAP_SHARE * gap

    duration <= budget                 -> "fit"       (pad with silence)
    duration <= budget * SOFT_SPEEDUP  -> "sped_up"   (ffmpeg atempo, pitch unchanged)
    otherwise                          -> ask the LLM to shorten, re-synthesize, re-check
                                          (up to MAX_REWRITES times)   -> "rewritten" if it then fits
    still too long:
        shortest <= budget * HARD_SPEEDUP -> "sped_up" (atempo up to 1.25)
        otherwise                         -> "flagged" (keep the shortest version, never cut words)

Design: the DECISIONS are pure functions (numbers in, decision out; tested offline).
The ACTIONS (speak, shorten, speed up, pad) are passed in as functions, so the
agent can be tested with fakes and run for real with Gnani + Gemini + ffmpeg.
Thresholds are starting values from the brief, to be tuned by ear.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable

GAP_SHARE = 0.5
SOFT_SPEEDUP = 1.15
HARD_SPEEDUP = 1.25
MAX_REWRITES = 3
SHORTEN_MARGIN = 0.95  # aim slightly under the budget when asking for a shorter line

# Fill short lines (added 2026-11-07 after watching the 2-min demo): the cloned voice
# often finished in ~60-70% of the original speaking time, leaving silence while the
# speaker's mouth still moves. If a fitting clip is shorter than FILL_IF x slot, slow it
# down toward the slot, but never below MIN_SLOWDOWN (still sounds natural).
FILL_IF = 0.9
MIN_SLOWDOWN = 0.85   # was 0.9; lowered 2026-11-08 (team: lips still moving after the voice stops)

# Expand very short lines (added 2026-11-08): if a fitting clip fills less than EXPAND_IF of the
# original speaking time, ask the LLM ONCE for a fuller, natural version (same meaning, no new
# facts), aiming at ~FILL_TARGET of the slot. Kept only if it still fits the budget.
EXPAND_IF = 0.75
FILL_TARGET = 0.92
MAX_EXPAND = 1.5      # never ask for more than 1.5x the characters


# --------------------------------------------------------------------------
# Pure decisions
# --------------------------------------------------------------------------

def budget_for(slot: float, gap: float) -> float:
    return slot + GAP_SHARE * max(gap, 0.0)


@dataclass(frozen=True)
class Decision:
    action: str          # "fit" | "speed" | "rewrite" | "flag"
    tempo: float = 1.0   # speed factor for "speed" (1.10 = 10% faster)


def decide(duration: float, budget: float, rewrites_done: int) -> Decision:
    """What to do with a clip of `duration` seconds that must fit in `budget` seconds."""
    if duration <= budget:
        return Decision("fit")
    ratio = duration / budget
    if ratio <= SOFT_SPEEDUP:
        return Decision("speed", round(ratio, 4))
    if rewrites_done < MAX_REWRITES:
        return Decision("rewrite")
    if ratio <= HARD_SPEEDUP:
        return Decision("speed", round(ratio, 4))
    return Decision("flag")


def fill_tempo(duration: float, slot: float) -> float:
    """Tempo (< 1 = slower) to stretch a too-short clip toward the original speaking time."""
    if slot <= 0 or duration >= slot * FILL_IF:
        return 1.0
    return round(max(duration / slot, MIN_SLOWDOWN), 4)


def wants_expansion(duration: float, slot: float) -> bool:
    return slot > 0 and duration < slot * EXPAND_IF


def expand_target_chars(current_chars: int, duration: float, slot: float) -> int:
    """Characters to ask for so the line fills about FILL_TARGET of the slot (capped at MAX_EXPAND x)."""
    want = int(current_chars * (slot * FILL_TARGET) / max(duration, 0.1))
    return max(min(want, int(current_chars * MAX_EXPAND)), current_chars + 1)


def target_chars(current_chars: int, duration: float, budget: float) -> int:
    """How many characters to ask for so the spoken line should fit (assumes speed stays constant)."""
    return max(int(current_chars * (budget / duration) * SHORTEN_MARGIN), 5)


# --------------------------------------------------------------------------
# The agent loop
# --------------------------------------------------------------------------

@dataclass
class Attempt:
    text: str
    chars: int
    duration: float


@dataclass
class TimingResult:
    unit_id: int
    status: str                    # fit | sped_up | rewritten | flagged | failed
    text: str                      # final spoken text
    budget: float
    raw_duration: float            # duration of the chosen clip before speed-up/padding
    tempo: float                   # 1.0 = unchanged
    final_duration: float          # after speed-up (before padding)
    rewrites: int
    attempts: list[Attempt] = field(default_factory=list)
    audio: bytes | None = None     # final WAV (padded to the budget when it fits)
    note: str = ""
    expanded: bool = False         # a fuller version replaced a too-short line

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("audio")
        return d


def fit_unit(
    unit_id: int,
    text: str,
    slot: float,
    gap: float,
    *,
    synthesize: Callable[[str], bytes],
    measure: Callable[[bytes], float],
    shorten: Callable[[str, int], str],
    speed_up: Callable[[bytes, float], bytes],
    pad: Callable[[bytes, float], bytes],
    expand: Callable[[str, int], str] | None = None,
    log: Callable[[str], None] = print,
) -> TimingResult:
    """Run the timing ladder for one unit. Exceptions from `synthesize` propagate
    (the caller marks the unit failed); a failing `shorten` just ends the rewrites."""
    budget = budget_for(slot, gap)
    attempts: list[Attempt] = []
    clips: list[bytes] = []

    def speak(t: str) -> None:
        audio = synthesize(t)
        attempts.append(Attempt(t, len(t), round(measure(audio), 3)))
        clips.append(audio)

    speak(text)
    rewrites = 0          # real number of rewrites done (for the report)
    can_rewrite = True    # becomes False if shortening fails or stops helping
    note = ""
    while True:
        cur = attempts[-1]
        d = decide(cur.duration, budget, rewrites if can_rewrite else MAX_REWRITES)
        if d.action == "fit":
            status = "rewritten" if rewrites else "fit"
            chosen, chosen_clip, expanded = cur, clips[-1], False
            if expand is not None and rewrites == 0 and wants_expansion(cur.duration, slot):
                want = expand_target_chars(cur.chars, cur.duration, slot)
                log(f"  unit {unit_id}: {cur.duration:.2f}s fills only {cur.duration / slot:.0%} of the "
                    f"{slot:.2f}s slot, asking for a fuller line (~{want} chars)")
                try:
                    fuller = expand(cur.text, want).strip()
                except Exception as e:  # LLM trouble: keep the short line, still slow it down
                    fuller, note = "", f"expand failed: {str(e)[:120]}"
                if fuller and fuller != cur.text and len(fuller) > cur.chars:
                    speak(fuller)
                    new = attempts[-1]
                    if cur.duration < new.duration <= budget:
                        chosen, chosen_clip, expanded = new, clips[-1], True
                    else:
                        note = (f"fuller version {new.duration:.2f}s did not fit (budget {budget:.2f}s); "
                                f"kept the original")
            r = _finish(unit_id, status, chosen, chosen_clip, budget, fill_tempo(chosen.duration, slot),
                        rewrites, attempts, pad, measure, note, speed_up)
            r.expanded = expanded
            return r
        if d.action == "speed" and rewrites == 0:
            return _finish(unit_id, "sped_up", cur, clips[-1], budget, d.tempo, 0, attempts, pad, measure,
                           note, speed_up)
        if d.action == "speed" and d.tempo <= SOFT_SPEEDUP:
            # a rewrite got it close enough that a light speed-up finishes the job
            return _finish(unit_id, "rewritten", cur, clips[-1], budget, d.tempo, rewrites, attempts, pad,
                           measure, note, speed_up)
        if d.action == "rewrite":
            want = target_chars(cur.chars, cur.duration, budget)
            log(f"  unit {unit_id}: {cur.duration:.2f}s > budget {budget:.2f}s, asking for <= {want} chars "
                f"(rewrite {rewrites + 1}/{MAX_REWRITES})")
            try:
                shorter = shorten(cur.text, want).strip()
            except Exception as e:  # LLM trouble: stop rewriting, use what we have
                note = f"shorten failed: {str(e)[:120]}"
                log(f"  unit {unit_id}: {note}")
                can_rewrite = False
                continue
            if not shorter or shorter == cur.text:
                note = "shorten returned the same/empty text"
                can_rewrite = False
                continue
            rewrites += 1
            speak(shorter)
            continue
        # Out of rewrites and still too long: use the SHORTEST version we produced.
        best_i = min(range(len(attempts)), key=lambda i: attempts[i].duration)
        best, best_clip = attempts[best_i], clips[best_i]
        ratio = best.duration / budget
        if ratio <= 1.0:
            return _finish(unit_id, "rewritten" if rewrites else "fit", best, best_clip, budget, 1.0,
                           rewrites, attempts, pad, measure, note)
        if ratio <= HARD_SPEEDUP:
            return _finish(unit_id, "sped_up", best, best_clip, budget, round(ratio, 4), rewrites, attempts,
                           pad, measure, note, speed_up)
        return TimingResult(unit_id, "flagged", best.text, round(budget, 3), best.duration, 1.0, best.duration,
                            rewrites, attempts, best_clip,
                            note or f"still {ratio:.2f}x the budget after {rewrites} rewrites")


def _finish(unit_id, status, att: Attempt, clip: bytes, budget: float, tempo: float, rewrites: int,
            attempts, pad, measure, note, speed_up=None) -> TimingResult:
    if tempo != 1.0:  # > 1 = faster (too long), < 1 = slower (filling a short line)
        clip = speed_up(clip, tempo)
    final = round(measure(clip), 3)
    padded = pad(clip, budget) if final < budget else clip
    return TimingResult(unit_id, status, att.text, round(budget, 3), att.duration, tempo, final, rewrites,
                        attempts, padded, note)
