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

    mixed_script: str = ""   # letters from another Indian script found in the text

    @property
    def script_ok(self) -> bool:
        return self.script_ratio >= SCRIPT_OK_RATIO and not self.mixed_script

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


INDIC_RANGE = (0x0900, 0x0DFF)  # Devanagari ... Sinhala: all Indian script blocks


def foreign_indic_chars(text: str, lang: str) -> str:
    """Letters from ANOTHER Indian script (e.g. Devanagari inside Bengali). Even one confuses TTS."""
    lo, hi = LANGUAGES[lang][2], LANGUAGES[lang][3]
    return "".join(ch for ch in text
                   if INDIC_RANGE[0] <= ord(ch) <= INDIC_RANGE[1] and not lo <= ord(ch) <= hi
                   and unicodedata.category(ch)[0] in "LM")


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


MIXED_SCRIPT_FIX = """

Your previous answer was:
\"\"\"
{previous}
\"\"\"
It contains letters from the wrong script: "{bad}". Write EVERY word, including names, using only {script} letters (spell names by their sound)."""


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
                       digits_found=has_digits(text), script_ratio=round(script_ratio(text, lang), 3),
                       mixed_script=foreign_indic_chars(text, lang))


SHORTEN_PROMPT = """This {lang_name} line is a dub of a Hindi video, but it takes too long to say.

Hindi original (for meaning):
\"\"\"
{source}
\"\"\"

Current {lang_name} line ({chars} characters):
\"\"\"
{current}
\"\"\"

Rewrite it in natural spoken {lang_name} with AT MOST {target} characters.
Rules:
- Keep the core meaning; drop filler words and repetition first.
- Write in {script} script only. Numbers as {lang_name} words, no digits. Keep names.{names_rule}
- Output only the spoken line.

Return JSON: {{"translation": "..."}}"""


def shorten_line(llm, lang: str, source: str, current: str, target: int,
                 names: list[str] | None = None) -> str:
    """Ask Gemini for a shorter version of a translated line (used by the Timing Agent)."""
    name, script = LANGUAGES[lang][0], LANGUAGES[lang][1]
    names_rule = f" Names: {', '.join(names)}." if names else ""
    prompt = SHORTEN_PROMPT.format(lang_name=name, script=script, source=source, current=current,
                                   chars=len(current), target=target, names_rule=names_rule)
    ans = llm.ask_json(prompt, TRANSLATE_SCHEMA, what=f"shorten -> {lang} ({len(current)}->{target} ch)")
    return " ".join(ans["translation"].split()).strip().strip('"').strip()


# --------------------------------------------------------------------------
# Gemini step
# --------------------------------------------------------------------------

def translate_units(units: list[Unit], lang: str, llm, *, names: list[str] | None = None,
                    context_units: list[Unit] | None = None, warn=print) -> list[Translation]:
    """Translate every unit in `units`. A failed unit is marked with `error` and the rest continue.

    context_units: the whole transcript for context (default: `units` itself). Lets you
    re-translate a few units while Gemini still sees the full video.
    """
    context = context_units or units
    if lang not in LANGUAGES:
        raise ValueError(f"unsupported language {lang!r}; use one of {list(LANGUAGES)}")
    names = names or []
    out: list[Translation] = []
    for u in units:
        try:
            prompt = build_prompt(u, context, lang, names)
            # wrong-script answers are not cached and the next model is tried (see LLM.ask_json)
            valid = lambda a: isinstance(a, dict) and not foreign_indic_chars(str(a.get("translation", "")), lang)
            ans = llm.ask_json(prompt, TRANSLATE_SCHEMA, what=f"translate unit {u.id} -> {lang}", validate=valid)
            t = check(u, lang, ans["translation"])
            if t.mixed_script:  # one targeted re-ask: tell Gemini exactly which letters are wrong
                fix = MIXED_SCRIPT_FIX.format(bad=t.mixed_script, previous=t.text, script=LANGUAGES[lang][1])
                ans = llm.ask_json(prompt + fix, TRANSLATE_SCHEMA, what=f"translate unit {u.id} -> {lang} (script fix)",
                                   validate=valid)
                t = check(u, lang, ans["translation"])
        except Exception as e:  # one bad unit must not kill the run
            warn(f"WARNING: unit {u.id} ({lang}) translation failed: {e}")
            t = Translation(u.id, lang, u.text, "", 0, char_budget(u.slot, lang), False, False, 0.0,
                            error=str(e)[:300])
        else:
            if t.digits_found:
                warn(f"WARNING: unit {u.id} ({lang}) contains digits: {t.text[:60]}")
            if t.mixed_script:
                warn(f"WARNING: unit {u.id} ({lang}) has letters from another script: {t.mixed_script!r}")
            elif not t.script_ok:
                warn(f"WARNING: unit {u.id} ({lang}) only {t.script_ratio:.0%} in {LANGUAGES[lang][1]} script")
        out.append(t)
    return out
