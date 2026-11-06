"""Offline tests for Stage 6 (translation). No network."""

import pytest

from src.translate import (build_prompt, char_budget, check, has_digits, script_ratio,
                           translate_units)
from src.units import Unit


def unit(i, slot, text):
    return Unit(id=i, start=0, end=slot, slot=slot, gap=0, text_raw=text, text=text)


UNITS = [unit(0, 14.52, "नमस्ते दोस्तों, आज दो कप चाय बनाएंगे।"), unit(1, 3.0, "चलिए शुरू करते हैं।")]


def test_char_budget_uses_language_speed():
    assert char_budget(10, "ta-IN") == int(10 * 17.7 * 0.9)
    assert char_budget(10, "bn-IN") < char_budget(10, "ta-IN")
    assert char_budget(0.1, "mr-IN") == 10  # never below a floor


@pytest.mark.parametrize("text,lang,expected", [
    ("வணக்கம் நண்பர்களே", "ta-IN", 1.0),
    ("নমস্কার বন্ধুরা", "bn-IN", 1.0),
    ("नमस्कार मित्रांनो", "mr-IN", 1.0),
    ("नमस्ते दोस्तों", "ta-IN", 0.0),  # Hindi script is not Tamil
])
def test_script_ratio(text, lang, expected):
    assert script_ratio(text, lang) == expected


def test_mixed_script_ratio_is_partial():
    r = script_ratio("வணக்கம் video", "ta-IN")
    assert 0.3 < r < 0.9


@pytest.mark.parametrize("text,expected", [("இரண்டு கப்", False), ("2 கப்", True), ("৫ কাপ", True)])
def test_digits_detected_in_any_script(text, expected):
    assert has_digits(text) is expected


def test_prompt_contains_context_budget_and_names():
    p = build_prompt(UNITS[1], UNITS, "ta-IN", ["गोकुल"])
    assert "नमस्ते दोस्तों" in p          # full transcript as context
    assert "चलिए शुरू करते हैं।" in p
    assert str(char_budget(3.0, "ta-IN")) in p
    assert "गोकुल" in p and "Tamil script" in p


def test_prompt_without_names_has_no_names_line():
    assert "Names in this video" not in build_prompt(UNITS[0], UNITS, "bn-IN", [])


def test_check_flags_problems():
    t = check(UNITS[1], "ta-IN", '  "2 கப் டீ   வீடியோ" ')
    assert t.text == "2 கப் டீ வீடியோ"        # quotes + extra spaces cleaned
    assert t.digits_found and t.script_ok


def test_over_budget_flag():
    t = check(UNITS[1], "bn-IN", "অ" * 200)
    assert t.over_budget and t.chars == 200


class FakeLLM:
    def __init__(self, answers):
        self.answers = list(answers)

    def ask_json(self, prompt, schema=None, what=""):
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return {"translation": a}


def test_one_failed_unit_does_not_stop_the_rest():
    warnings = []
    out = translate_units(UNITS, "ta-IN", FakeLLM([RuntimeError("503"), "வாங்க ஆரம்பிக்கலாம்."]),
                          warn=warnings.append)
    assert out[0].error and out[0].text == ""
    assert out[1].text == "வாங்க ஆரம்பிக்கலாம்." and out[1].error is None
    assert "failed" in warnings[0]


def test_wrong_script_is_warned():
    warnings = []
    translate_units(UNITS[:1], "ta-IN", FakeLLM(["नमस्ते"]), warn=warnings.append)
    assert any("script" in w for w in warnings)


def test_unknown_language_rejected():
    with pytest.raises(ValueError):
        translate_units(UNITS, "fr-FR", FakeLLM([]))
