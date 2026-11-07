"""Offline tests for the Timing Agent. Fake audio: the 'clip' is just its duration.

No network, no ffmpeg, no credits. Every branch of the ladder is covered.
"""

import pytest

from src.timing import (HARD_SPEEDUP, MAX_REWRITES, SOFT_SPEEDUP, Decision, budget_for, decide,
                        fit_unit, target_chars)


# ------------------------------------------------------------ decisions ----

def test_budget_uses_half_the_gap():
    assert budget_for(10.0, 2.0) == 11.0
    assert budget_for(10.0, -1.0) == 10.0  # negative gaps never shrink the slot


@pytest.mark.parametrize("duration,rewrites,expected", [
    (9.0, 0, Decision("fit")),
    (10.0, 0, Decision("fit")),                 # exactly on budget
    (11.0, 0, Decision("speed", 1.1)),          # 10% over
    (11.5, 0, Decision("speed", 1.15)),         # exactly the soft limit
    (11.6, 0, Decision("rewrite")),             # just over the soft limit
    (11.6, MAX_REWRITES, Decision("speed", 1.16)),  # out of rewrites -> hard speed-up allowed
    (12.5, MAX_REWRITES, Decision("speed", 1.25)),
    (12.6, MAX_REWRITES, Decision("flag")),
])
def test_decide(duration, rewrites, expected):
    assert decide(duration, 10.0, rewrites) == expected


def test_target_chars_scales_with_overrun():
    assert target_chars(200, 20.0, 10.0) == int(200 * 0.5 * 0.95)
    assert target_chars(3, 100.0, 1.0) == 5  # floor


# ------------------------------------------------------------ the agent ----

class FakeWorld:
    """Pretend TTS: a line lasts len(text) * secs_per_char seconds.
    A clip is represented as its duration (as bytes) so tests can read it back."""

    def __init__(self, secs_per_char=0.1, shorten_to=None, shorten_error=None):
        self.spc = secs_per_char
        self.shorten_to = list(shorten_to or [])
        self.shorten_error = shorten_error
        self.spoken, self.shorten_calls, self.tempos = [], [], []

    @staticmethod
    def enc(seconds):
        return f"{seconds:.6f}".encode()

    def synthesize(self, text):
        self.spoken.append(text)
        return self.enc(len(text) * self.spc)

    def measure(self, clip):
        return float(clip.decode())

    def shorten(self, text, want):
        self.shorten_calls.append(want)
        if self.shorten_error:
            raise self.shorten_error
        return self.shorten_to.pop(0) if self.shorten_to else text

    def speed_up(self, clip, tempo):
        self.tempos.append(tempo)
        return self.enc(self.measure(clip) / tempo)

    def pad(self, clip, seconds):
        return self.enc(max(self.measure(clip), seconds))

    def run(self, text, slot, gap=0.0, expand=None):
        return fit_unit(0, text, slot, gap, synthesize=self.synthesize, measure=self.measure,
                        shorten=self.shorten, speed_up=self.speed_up, pad=self.pad, expand=expand,
                        log=lambda m: None)


def test_fit_pads_to_budget():
    w = FakeWorld()
    r = w.run("x" * 95, slot=10.0)                 # 9.5 s in a 10 s budget (>= 90%: no slow-down)
    assert r.status == "fit" and r.tempo == 1.0 and r.rewrites == 0
    assert w.measure(r.audio) == 10.0               # padded with silence to the budget
    assert w.shorten_calls == [] and w.tempos == []


def test_short_line_is_slowed_a_little_to_fill_the_slot():
    w = FakeWorld()
    r = w.run("x" * 60, slot=10.0)                 # 6 s in a 10 s slot -> slow, but max 0.85x
    assert r.status == "fit" and r.tempo == 0.85
    assert r.final_duration == pytest.approx(6.0 / 0.85, abs=0.001)  # durations are rounded to ms
    r2 = FakeWorld().run("x" * 87, slot=10.0)      # 8.7 s: 0.87x is enough (above the 0.85 floor)
    assert r2.tempo == 0.87 and r2.final_duration == pytest.approx(10.0, abs=0.001)


@pytest.mark.parametrize("duration,slot,expected", [
    (9.0, 10.0, 1.0),      # 90% of slot: leave it
    (8.95, 10.0, 0.895),   # just under: stretch exactly to the slot
    (5.0, 10.0, 0.85),     # far too short: floor 0.85
    (9.5, 10.0, 1.0),
    (3.0, 0.0, 1.0),       # no slot info: leave it
])
def test_fill_tempo(duration, slot, expected):
    from src.timing import fill_tempo
    assert fill_tempo(duration, slot) == expected


# ---------------------------------------------------------- expansion ----

def test_too_short_line_gets_a_fuller_version():
    w, asked = FakeWorld(), []
    def expand(text, want):
        asked.append(want)
        return "y" * 85                             # 8.5 s fuller line
    r = w.run("x" * 50, slot=10.0, expand=expand)   # 5 s = 50 % of the slot (< 75 %)
    assert r.expanded and r.text == "y" * 85 and r.status == "fit"
    assert asked == [75]                            # min(50*9.2/5=92, 50*1.5=75)
    assert r.tempo == 0.85 and r.final_duration == pytest.approx(8.5 / 0.85, abs=0.001)


def test_fuller_version_that_does_not_fit_is_dropped():
    w = FakeWorld()
    r = w.run("x" * 50, slot=10.0, expand=lambda t, n: "y" * 130)   # 13 s > 10 s budget
    assert not r.expanded and r.text == "x" * 50 and "did not fit" in r.note
    assert r.tempo == 0.85                          # original still slowed a little


def test_expand_failure_keeps_the_original():
    def boom(t, n):
        raise RuntimeError("quota")
    r = FakeWorld().run("x" * 50, slot=10.0, expand=boom)
    assert not r.expanded and "expand failed" in r.note and r.text == "x" * 50


def test_no_expansion_when_line_already_fills_most_of_the_slot():
    calls = []
    FakeWorld().run("x" * 80, slot=10.0, expand=lambda t, n: calls.append(1) or "y" * 90)  # 80 % >= 75 %
    assert calls == []


def test_expand_target_is_capped():
    from src.timing import expand_target_chars
    assert expand_target_chars(100, 2.0, 10.0) == 150          # would be 460: capped at 1.5x
    assert expand_target_chars(100, 7.0, 10.0) == 131          # 100*9.2/7


def test_gap_gives_extra_room():
    r = FakeWorld().run("x" * 105, slot=10.0, gap=2.0)  # 10.5 s; budget 11 s
    assert r.status == "fit" and r.budget == 11.0


def test_slightly_long_is_sped_up():
    w = FakeWorld()
    r = w.run("x" * 110, slot=10.0)                # 11 s: 10% over
    assert r.status == "sped_up" and r.tempo == 1.1
    assert r.final_duration == pytest.approx(10.0)
    assert w.shorten_calls == []                    # no LLM needed


def test_too_long_is_rewritten_then_fits():
    w = FakeWorld(shorten_to=["y" * 90])
    r = w.run("x" * 150, slot=10.0)                # 15 s -> rewrite -> 9 s
    assert r.status == "rewritten" and r.rewrites == 1 and r.text == "y" * 90
    assert w.shorten_calls == [int(150 * (10 / 15) * 0.95)]
    assert [a.duration for a in r.attempts] == [15.0, 9.0]


def test_rewrite_plus_light_speedup_counts_as_rewritten():
    w = FakeWorld(shorten_to=["y" * 108])
    r = w.run("x" * 150, slot=10.0)                # 15 s -> 10.8 s -> speed 1.08
    assert r.status == "rewritten" and r.tempo == 1.08


def test_three_rewrites_then_hard_speedup_on_shortest():
    w = FakeWorld(shorten_to=["a" * 130, "b" * 122, "c" * 125])   # never under 11.5 s
    r = w.run("x" * 150, slot=10.0)
    assert r.rewrites == MAX_REWRITES and len(w.shorten_calls) == MAX_REWRITES
    assert r.status == "sped_up" and r.text == "b" * 122           # the SHORTEST version
    assert r.tempo == pytest.approx(1.22) and r.tempo <= HARD_SPEEDUP


def test_hopeless_line_is_flagged_and_keeps_shortest():
    w = FakeWorld(shorten_to=["a" * 160, "b" * 140, "c" * 150])
    r = w.run("x" * 200, slot=10.0)                # 20 s; best rewrite 14 s = 1.4x
    assert r.status == "flagged" and r.text == "b" * 140
    assert r.tempo == 1.0 and w.tempos == []       # no extreme speed-up, words never cut
    assert "1.40x" in r.note


def test_shorten_failure_stops_rewrites_but_not_the_unit():
    w = FakeWorld(shorten_error=RuntimeError("Gemini 503"))
    r = w.run("x" * 120, slot=10.0)                # 12 s = 1.2x -> needs rewrite, LLM fails
    assert r.status == "sped_up" and r.tempo == 1.2  # falls back to hard speed-up
    assert r.rewrites == 0 and "shorten failed" in r.note
    assert len(w.shorten_calls) == 1


def test_shorten_returning_same_text_stops_looping():
    w = FakeWorld(shorten_to=["x" * 200])
    r = w.run("x" * 200, slot=10.0)
    assert r.status == "flagged" and r.rewrites == 0
    assert len(w.spoken) == 1                       # never re-synthesized the identical text


def test_synthesis_error_propagates_to_caller():
    w = FakeWorld()

    def broken(text):
        raise RuntimeError("TTS 500")

    with pytest.raises(RuntimeError):
        fit_unit(0, "hello", 5, 0, synthesize=broken, measure=w.measure, shorten=w.shorten,
                 speed_up=w.speed_up, pad=w.pad, log=lambda m: None)


def test_thresholds_are_the_brief_starting_values():
    assert (SOFT_SPEEDUP, HARD_SPEEDUP, MAX_REWRITES) == (1.15, 1.25, 3)
