"""Offline tests for the Gemini wrapper. No network, no quota used."""

import json
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
        return SimpleNamespace(status_code=status, text=str(body), json=lambda: body)


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


def test_wrong_model_stops_the_run(make_llm):
    m = make_llm([(404, {"error": "not found"})])
    with pytest.raises(FatalAPIError, match="GEMINI_MODEL"):
        m.ask_json("q")
