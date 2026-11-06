"""Stage 6: translate each unit into Tamil / Bengali / Marathi with Gemini.

One Gemini call per unit (brief), with the whole transcript as context.
Rules given to the model: natural spoken style, numbers as words (no digits),
names kept (written in the target script), stay under a character budget.

Every result is checked (never fatal; problems are flagged for later stages):
  digits_found  -> raw digits get mispronounced by TTS (Gnani docs)
  script_ratio  -> share of letters in the target script (catches wrong-language replies)
  over_budget   -> longer than the character budget (the timing agent will deal with it)
"""

from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass

from .units import Unit

LANGUAGES = {
    # code: (name, script name, Unicode block start, end)
    "ta-IN": ("Tamil", "Tamil", 0x0B80, 0x0BFF),
    "bn-IN": ("Bengali", "Bengali", 0x0980, 0x09FF),
    "mr-IN": ("Marathi", "Devanagari", 0x0900, 0x097F),
}

# Characters per second spoken by OUR cloned voice, from the Stage 1 voice test
# (ONE sentence per language, so rough starting values; refine with real data).
CHARS_PER_SECOND = {"ta-IN": 17.7, "bn-IN": 13.5, "mr-IN": 14.7}
BUDGET_SAFETY = 0.9
SCRIPT_OK_RATIO = 0.8


@dataclass
class Translation:
    id: int
    lang: str
    source: str
    text: str
    chars: int
    budget_chars: int
    over_budget: bool
    digits_found: bool
    script_ratio: float
    error: str | None = None

    @property
    def script_ok(self) -> bool:
        return self.script_ratio >= SCRIPT_OK_RATIO

    def to_dict(self) -> dict:
        return asdict(self) | {"script_ok": self.script_ok}


# --------------------------------------------------------------------------
# Pure helpers (tested offline)
# --------------------------------------------------------------------------

def char_budget(slot: float, lang: str) -> int:
    return max(int(slot * CHARS_PER_SECOND[lang] * BUDGET_SAFETY), 10)


def script_ratio(text: str, lang: str) -> float:
    """Share of letters (incl. vowel signs) that belong to the target script's Unicode block."""
    lo, hi = LANGUAGES[lang][2], LANGUAGES[lang][3]
    letters = [ch for ch in text if unicodedata.category(ch)[0] in "LM"]
    if not letters:
        return 0.0
    return sum(lo <= ord(ch) <= hi for ch in letters) / len(letters)


def has_digits(text: str) -> bool:
    """ASCII digits or any Unicode decimal digit (e.g. Tamil ௫, Bengali ৫)."""
    return any(unicodedata.category(ch) == "Nd" for ch in text)


TRANSLATE_SCHEMA = {
    "type": "object",
    "properties": {"translation": {"type": "string"}},
    "required": ["translation"],
}

TRANSLATE_PROMPT = """You are dubbing a short Hindi video into {lang_name}. The speaker talks casually (Hinglish; English words may be written in Devanagari).

Full transcript, for context only:
\"\"\"
{context}
\"\"\"

Translate ONLY this line into natural, spoken {lang_name}, the way a {lang_name} creator would say it on camera:
\"\"\"
{line}
\"\"\"

Rules:
- Write in {script} script only.
- Keep the same meaning and tone. Common English words people really say (like video, voice, test) may stay, written in {script} script.
- Write every number as {lang_name} words. No digits at all.
- Names must not be translated; write them in {script} script so they sound the same.{names_rule}
- Keep it short: at most {budget} characters. Shorter is better if the meaning stays.
- Output only the spoken line: no quotes, notes or transliteration.

Return JSON: {{"translation": "..."}}"""


def build_prompt(unit: Unit, all_units: list[Unit], lang: str, names: list[str]) -> str:
    name, script = LANGUAGES[lang][0], LANGUAGES[lang][1]
    names_rule = f"\n- Names in this video (spell them correctly): {', '.join(names)}" if names else ""
    return TRANSLATE_PROMPT.format(
        lang_name=name, script=script, context="\n".join(u.text for u in all_units),
        line=unit.text, budget=char_budget(unit.slot, lang), names_rule=names_rule)


def check(unit: Unit, lang: str, text: str) -> Translation:
    text = " ".join(text.split()).strip().strip('"').strip()
    budget = char_budget(unit.slot, lang)
    return Translation(id=unit.id, lang=lang, source=unit.text, text=text, chars=len(text),
                       budget_chars=budget, over_budget=len(text) > budget,
                       digits_found=has_digits(text), script_ratio=round(script_ratio(text, lang), 3))


# --------------------------------------------------------------------------
# Gemini step
# --------------------------------------------------------------------------

def translate_units(units: list[Unit], lang: str, llm, *, names: list[str] | None = None,
                    warn=print) -> list[Translation]:
    """Translate every unit. A failed unit is marked with `error` and the rest continue."""
    if lang not in LANGUAGES:
        raise ValueError(f"unsupported language {lang!r}; use one of {list(LANGUAGES)}")
    names = names or []
    out: list[Translation] = []
    for u in units:
        try:
            ans = llm.ask_json(build_prompt(u, units, lang, names), TRANSLATE_SCHEMA,
                               what=f"translate unit {u.id} -> {lang}")
            t = check(u, lang, ans["translation"])
        except Exception as e:  # one bad unit must not kill the run
            warn(f"WARNING: unit {u.id} ({lang}) translation failed: {e}")
            t = Translation(u.id, lang, u.text, "", 0, char_budget(u.slot, lang), False, False, 0.0,
                            error=str(e)[:300])
        else:
            if t.digits_found:
                warn(f"WARNING: unit {u.id} ({lang}) contains digits: {t.text[:60]}")
            if not t.script_ok:
                warn(f"WARNING: unit {u.id} ({lang}) only {t.script_ratio:.0%} in {LANGUAGES[lang][1]} script")
        out.append(t)
    return out
