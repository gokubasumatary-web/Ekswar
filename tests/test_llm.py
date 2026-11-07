"""Offline tests for the Gemini wrapper. No network, no quota used."""

import json
import json as _json  # FakeSession.post has a parameter named `json` (like requests), which hides the module
from types import SimpleNamespace

import pytest

from src import llm as llm_mod
from src.cache import Cache
from src.retry import FatalAPIError, RequestError


def reply(text, finish="STOP", thought=None):
    parts = ([{"text": thought, "thought": True}] if thought else []) + [{"text": text}]
    return {"candidates": [{"content": {"parts": parts}, "finishReason": finish}]}


class FakeSession:
    def __init__(self, replies):
        self.replies = list(replies)
        self.bodies = []
        self.headers = {}

    def post(self, url, json, timeout):
        self.bodies.append(json)
        self.urls = getattr(self, "urls", []) + [url]
        if not self.replies:
            raise AssertionError("unexpected extra request")
        status, body = self.replies.pop(0)
        return SimpleNamespace(status_code=status, text=_json.dumps(body, ensure_ascii=False), json=lambda: body)


@pytest.fixture
def make_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)  # don't inherit the real .env

    def make(replies, fallback=None):
        if fallback:
            monkeypatch.setenv("GEMINI_FALLBACK_MODEL", fallback)
        m = llm_mod.LLM(cache=Cache(tmp_path / "c"), on_retry=None, log=lambda s: None)
        m.session = FakeSession(replies)
        m.sleep = lambda s: None
        return m
    return make


def test_body_requests_json_and_low_thinking():
    b = llm_mod.build_body("hi", {"type": "object"})
    g = b["generationConfig"]
    assert g["responseMimeType"] == "application/json"
    assert g["responseJsonSchema"] == {"type": "object"}
    assert g["thinkingConfig"]["thinkingLevel"] == "LOW"
    assert "temperature" not in g


def test_thought_parts_are_ignored():
    assert llm_mod.extract_text(reply('{"a": 1}', thought="let me think")) == '{"a": 1}'


@pytest.mark.parametrize("body", [
    {"promptFeedback": {"blockReason": "SAFETY"}},
    {"candidates": []},
    reply('{"a": ', finish="MAX_TOKENS"),
])
def test_bad_answers_raise(body):
    with pytest.raises(RequestError):
        llm_mod.extract_text(body)


def test_fenced_json_tolerated():
    assert llm_mod.parse_json_text('```json\n{"ta": "வணக்கம்"}\n```') == {"ta": "வணக்கம்"}


def test_answer_cached(make_llm):
    m = make_llm([(200, reply(json.dumps({"ta": "வணக்கம்"})))])
    assert m.ask_json("q") == {"ta": "வணக்கம்"}
    assert m.ask_json("q") == {"ta": "வணக்கம்"}  # second time from disk
    assert m.api_calls == 1


def test_invalid_json_gets_one_strict_reask(make_llm):
    m = make_llm([(200, reply("Sure! here it is")), (200, reply('{"ok": true}'))])
    assert m.ask_json("q") == {"ok": True}
    assert llm_mod.STRICT_SUFFIX.strip() in m.session.bodies[1]["contents"][0]["parts"][0]["text"]


def test_503_overload_is_retried(make_llm):
    m = make_llm([(503, {"error": "busy"}), (503, {"error": "busy"}), (200, reply('{"x": 1}'))])
    assert m.ask_json("q") == {"x": 1}
    assert m.api_calls == 3


def test_busy_main_model_falls_back(make_llm):
    busy = (503, {"error": "busy"})
    m = make_llm([busy, busy, busy, (200, reply('{"ta": "வணக்கம்"}'))], fallback="backup-model")
    assert m.ask_json("q") == {"ta": "வணக்கம்"}
    assert m.api_calls == 4              # 3 tries on main (fewer than usual), then 1 on backup
    assert "backup-model" in m.session.urls[-1]
    assert m.fallback_used == 1
    assert m.ask_json("q") == {"ta": "வணக்கம்"}  # cached backup answer reused
    assert m.api_calls == 4


def test_timeouts_fall_back_too(make_llm):
    m = make_llm([], fallback="backup-model")
    calls = []

    def post(url, json, timeout):
        calls.append((url, timeout))
        if "test-model" in url:
            raise llm_mod.requests.Timeout("hung")
        return SimpleNamespace(status_code=200, text="", json=lambda: reply('{"ok": 1}'))

    m.session.post = post
    assert m.ask_json("q") == {"ok": 1}
    assert [t for u, t in calls if "test-model" in u] == [45.0] * 3  # shorter timeout on main


def test_blocked_prompt_does_not_waste_a_backup_call(make_llm):
    m = make_llm([(200, {"promptFeedback": {"blockReason": "SAFETY"}})], fallback="backup-model")
    with pytest.raises(RequestError, match="blocked"):
        m.ask_json("q")
    assert m.api_calls == 1


def test_no_fallback_configured_keeps_six_attempts(make_llm):
    busy = (503, {"error": "busy"})
    m = make_llm([busy] * 6)
    with pytest.raises(llm_mod.ModelUnavailable):
        m.ask_json("q")
    assert m.api_calls == 6


QUOTA = (429, {"error": {"code": 429, "message": "You exceeded your current quota, please check your plan"}})


def test_chain_of_backups_is_tried_in_order(make_llm):
    busy = (503, {"error": "busy"})
    m = make_llm([busy] * 3 + [busy] * 3 + [(200, reply('{"ok": 1}'))], fallback="backup-a, backup-b")
    assert m.ask_json("q") == {"ok": 1}
    assert m.fallback_models == ["backup-a", "backup-b"]
    assert "backup-b" in m.session.urls[-1] and m.api_calls == 7  # 3 + 3 + 1


DAILY = (429, {"error": {"code": 429, "message": "You exceeded your current quota, please check your plan",
                         "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
                             {"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}})
MINUTE = (429, {"error": {"code": 429, "message": "You exceeded your current quota, please check your plan",
                          "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
                              {"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}]},
                              {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "38s"}]}})


def test_quota_switches_model_immediately_without_retrying(make_llm):
    m = make_llm([QUOTA, (200, reply('{"ok": 1}'))], fallback="backup-model")
    assert m.ask_json("q") == {"ok": 1}
    assert m.api_calls == 2                      # NOT 3 retries on the model that hit its quota
    assert m.exhausted == set() and "test-model" in m.cooldown  # unknown details: pause, not dead


def test_paused_model_is_skipped_while_cooling_down(make_llm):
    m = make_llm([MINUTE, (200, reply('{"a": 1}')), (200, reply('{"b": 2}'))], fallback="backup-model")
    m.clock = lambda: 1000.0
    m.ask_json("first")
    assert m.cooldown["test-model"] == 1038.0     # used Google's retryDelay (38 s)
    m.ask_json("second")
    assert m.api_calls == 3 and all("backup-model" in u for u in m.session.urls[1:])


def test_paused_model_is_used_again_after_cooldown(make_llm):
    m = make_llm([MINUTE, (200, reply('{"a": 1}')), (200, reply('{"b": 2}'))], fallback="backup-model")
    t = [1000.0]
    m.clock = lambda: t[0]
    m.ask_json("first")
    t[0] = 1100.0                                  # 100 s later
    m.ask_json("second")
    assert "test-model" in m.session.urls[-1]      # main model is back


def test_daily_quota_skips_model_for_the_run(make_llm):
    m = make_llm([DAILY, DAILY], fallback="backup-model")
    with pytest.raises(llm_mod.ModelUnavailable):
        m.ask_json("q1")
    assert m.exhausted == {"test-model", "backup-model"}
    with pytest.raises(llm_mod.ModelUnavailable, match="daily quota"):
        m.ask_json("q2")                           # no calls at all now
    assert m.api_calls == 2


def test_all_models_paused_waits_for_the_first_free_one(make_llm):
    m = make_llm([MINUTE, MINUTE, (200, reply('{"ok": 1}'))], fallback="backup-model")
    m.clock = lambda: 1000.0
    waits = []
    m.sleep = waits.append
    assert m.ask_json("q1") == {"ok": 1}           # both hit per-minute quota -> wait -> retry -> ok
    assert waits == [38.0] and m.api_calls == 3


def test_invalid_answer_tries_next_model_and_is_not_cached(make_llm):
    m = make_llm([(200, reply('{"t": "bad"}')), (200, reply('{"t": "good"}'))], fallback="backup-model")
    ok = lambda a: a["t"] == "good"
    assert m.ask_json("q", validate=ok) == {"t": "good"}
    assert "backup-model" in m.session.urls[-1]
    assert m.ask_json("q", validate=ok) == {"t": "good"} and m.api_calls == 2   # good one cached


def test_all_invalid_returns_last_answer_uncached(make_llm):
    m = make_llm([(200, reply('{"t": "bad1"}')), (200, reply('{"t": "bad2"}')),
                  (200, reply('{"t": "good"}'))], fallback="backup-model")
    ok = lambda a: a["t"] == "good"
    assert m.ask_json("q", validate=ok) == {"t": "bad2"}   # caller will flag it
    assert m.ask_json("q", validate=ok) == {"t": "good"}   # NOT served from cache: asked again


def test_old_cached_invalid_answer_is_ignored(make_llm):
    m = make_llm([(200, reply('{"t": "bad"}')), (200, reply('{"t": "good"}'))])
    m.ask_json("q")                                          # cached without validation (old behaviour)
    assert m.ask_json("q", validate=lambda a: a["t"] == "good") == {"t": "good"}


def test_last_model_paused_waits_and_retries_once(make_llm):
    m = make_llm([MINUTE, (200, reply('{"ok": 1}'))])        # single model, per-minute quota
    m.clock = lambda: 1000.0
    waits = []
    m.sleep = waits.append
    assert m.ask_json("q") == {"ok": 1}                       # waited instead of failing the line
    assert waits == [38.0]


def test_quota_info_parsing():
    import json
    assert llm_mod.quota_info(json.dumps(DAILY[1]))[0] is True
    daily, cool, ids = llm_mod.quota_info(json.dumps(MINUTE[1]))
    assert (daily, cool) == (False, 38.0) and "PerMinute" in ids
    assert llm_mod.quota_info("not json") == (False, 60.0, "")


def test_burst_429_is_still_retried(make_llm):
    burst = (429, {"error": {"code": 429, "message": "Resource has been exhausted (e.g. check quota). Too many requests"}})
    m = make_llm([burst, (200, reply('{"ok": 1}'))], fallback="backup-model")
    assert m.ask_json("q") == {"ok": 1}
    assert m.exhausted == set() and "test-model" in m.session.urls[-1]


def test_wrong_model_stops_the_run(make_llm):
    m = make_llm([(404, {"error": "not found"})])
    with pytest.raises(FatalAPIError, match="GEMINI_MODEL"):
        m.ask_json("q")
