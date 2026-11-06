"""Offline tests for Stage 5 (units). No network."""

import pytest

from src.units import (build_units, make_units, merge_tiny, punctuate, same_words,
                       segments_from_transcript, words_only)


def seg(a, b, t):
    return {"start": a, "end": b, "text": t}


def test_segments_read_and_sorted():
    t = {"segments": [
        {"start_time": 5.0, "end_time": 7.0, "text": "दूसरा"},
        {"start_time": 0.2, "end_time": 4.0, "text": "पहला"},
        {"start_time": 8.0, "end_time": 9.0, "text": "  "},  # empty -> dropped
    ]}
    assert [s["text"] for s in segments_from_transcript(t)] == ["पहला", "दूसरा"]


def test_fallback_to_full_transcript_warns():
    warnings = []
    segs = segments_from_transcript({"full_transcript": "सब कुछ", "duration_seconds": 12.5},
                                    warn=warnings.append)
    assert segs == [seg(0.0, 12.5, "सब कुछ")]
    assert warnings and "no segments" in warnings[0]


def test_tiny_segment_merges_into_closer_neighbour():
    segs = [seg(0, 3, "a"), seg(3.1, 3.5, "b"), seg(5.0, 8, "c")]  # "b" is 0.4 s, closer to "a"
    assert merge_tiny(segs) == [seg(0, 3.5, "a b"), seg(5.0, 8, "c")]


def test_tiny_first_segment_merges_forward():
    assert merge_tiny([seg(0, 0.5, "hi"), seg(0.6, 4, "there")]) == [seg(0, 4, "hi there")]


def test_single_tiny_segment_is_kept():
    assert merge_tiny([seg(0, 0.5, "hi")]) == [seg(0, 0.5, "hi")]


def test_slot_and_gap_math():
    u = build_units([seg(0.2, 14.72, "x"), seg(14.99, 27.35, "y")], total_duration=27.35)
    assert (u[0].slot, u[0].gap) == (14.52, 0.27)
    assert (u[1].slot, u[1].gap) == (12.36, 0.0)  # last unit: until end of audio


def test_last_gap_uses_total_duration():
    u = build_units([seg(0, 5, "x")], total_duration=8.0)
    assert u[0].gap == 3.0


def test_words_only_keeps_hindi_vowel_signs():
    assert words_only("नमस्ते, दोस्तों! कैसे हो?") == "नमस्ते दोस्तों कैसे हो"
    assert words_only("ठीक है।") == "ठीक है"  # danda removed


def test_same_words_ignores_punctuation():
    assert same_words("नमस्ते दोस्तों कैसे हो", "नमस्ते दोस्तों, कैसे हो?") == 100


class FakeLLM:
    def __init__(self, lines=None, error=None):
        self.lines, self.error, self.prompts = lines, error, []

    def ask_json(self, prompt, schema=None, what=""):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return {"lines": self.lines}


def two_units():
    return build_units([seg(0, 5, "नमस्ते दोस्तों कैसे हो"), seg(6, 9, "चलिए शुरू करते हैं")], 10)


def test_punctuation_applied_when_words_unchanged():
    llm = FakeLLM(["1. नमस्ते दोस्तों, कैसे हो?", "चलिए शुरू करते हैं।"])
    u = punctuate(two_units(), llm, warn=lambda m: None)
    assert [x.text for x in u] == ["नमस्ते दोस्तों, कैसे हो?", "चलिए शुरू करते हैं।"]
    assert all(x.punctuation_ok for x in u)
    assert len(llm.prompts) == 1  # one call for the whole video


def test_reworded_line_is_rejected():
    warnings = []
    llm = FakeLLM(["नमस्ते मित्रों, आप सब कैसे हैं?", "चलिए शुरू करते हैं।"])  # changed words
    u = punctuate(two_units(), llm, warn=warnings.append)
    assert u[0].text == u[0].text_raw and not u[0].punctuation_ok
    assert u[1].text == "चलिए शुरू करते हैं।"
    assert "changed the words" in warnings[0]


@pytest.mark.parametrize("llm", [FakeLLM(["only one line"]), FakeLLM(error=RuntimeError("503"))])
def test_llm_problems_fall_back_to_raw_text(llm):
    u = punctuate(two_units(), llm, warn=lambda m: None)
    assert [x.text for x in u] == [x.text_raw for x in u]
    assert not any(x.punctuation_ok for x in u)


def test_make_units_without_llm():
    t = {"duration_seconds": 10, "segments": [{"start_time": 0, "end_time": 4, "text": "एक"}]}
    u = make_units(t)
    assert len(u) == 1 and u[0].gap == 6
