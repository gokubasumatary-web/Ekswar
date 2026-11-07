"""Offline tests for the foundation: cache + retry rules. No network, no API keys."""

from types import SimpleNamespace

import pytest

from src.cache import Cache, make_key
from src.retry import FatalAPIError, RequestError, call_with_retry


# ---------------------------------------------------------------- cache ----

def test_make_key_is_stable_and_sensitive():
    a = make_key("tts", {"text": "வணக்கம்", "rate": 44100}, b"\x01\x02")
    b = make_key("tts", {"rate": 44100, "text": "வணக்கம்"}, b"\x01\x02")  # dict order ignored
    c = make_key("tts", {"text": "வணக்கம்!", "rate": 44100}, b"\x01\x02")  # one char changed
    assert a == b
    assert a != c


def test_cache_round_trip_and_counters(tmp_path):
    cache = Cache(tmp_path)
    assert cache.get_json("embedding", "k1") is None
    cache.put_json("embedding", "k1", {"shape": [1, 768]})
    assert cache.get_json("embedding", "k1") == {"shape": [1, 768]}
    cache.put_bytes("tts", "k2", "wav", b"RIFF....")
    assert cache.get_bytes("tts", "k2", "wav") == b"RIFF...."
    assert (cache.hits, cache.misses) == (2, 1)


def test_compute_called_only_once(tmp_path):
    cache = Cache(tmp_path)
    calls = []

    def expensive():
        calls.append(1)
        return {"transcript": "नमस्ते"}

    first = cache.json_or_compute("stt", "k", expensive)
    second = cache.json_or_compute("stt", "k", expensive)
    assert first == second == {"transcript": "नमस्ते"}
    assert len(calls) == 1  # second call came from disk: no credits spent


def test_failed_compute_is_not_cached(tmp_path):
    cache = Cache(tmp_path)

    def boom():
        raise RequestError("HTTP 400")

    with pytest.raises(RequestError):
        cache.json_or_compute("stt", "k", boom)
    assert not cache.path("stt", "k", "json").exists()
    assert not list((tmp_path / "stt").glob(".tmp-*"))  # no leftover temp files


# ---------------------------------------------------------------- retry ----

def fake_sender(statuses):
    """Return a send() that replies with the given status codes in order."""
    replies = iter(statuses)
    log = []

    def send():
        s = next(replies)
        log.append(s)
        if isinstance(s, BaseException):
            raise s
        return SimpleNamespace(status_code=s, text=f"body {s}")

    return send, log


def no_sleep(_seconds):
    pass


def test_success_first_try():
    send, log = fake_sender([200])
    assert call_with_retry(send, what="t", sleep=no_sleep).status_code == 200
    assert log == [200]


def test_429_backs_off_then_succeeds():
    waits = []
    send, log = fake_sender([429, 429, 200])
    call_with_retry(send, what="t", sleep=waits.append)
    assert log == [429, 429, 200]
    assert waits == [2.0, 4.0]  # waits get longer each time


def test_500_is_retried_only_once():
    send, log = fake_sender([500, 500, 200])
    with pytest.raises(RequestError) as e:
        call_with_retry(send, what="TTS unit 3", sleep=no_sleep)
    assert log == [500, 500]
    assert e.value.status == 500


@pytest.mark.parametrize("status", [401, 402, 403])
def test_fatal_statuses_stop_immediately(status):
    send, log = fake_sender([status, 200])
    with pytest.raises(FatalAPIError):
        call_with_retry(send, what="t", sleep=no_sleep)
    assert log == [status]


def test_400_is_not_retried():
    send, log = fake_sender([400, 200])
    with pytest.raises(RequestError):
        call_with_retry(send, what="t", sleep=no_sleep)
    assert log == [400]


def test_gives_up_after_max_attempts():
    send, log = fake_sender([503] * 10)
    with pytest.raises(RequestError):
        call_with_retry(send, what="t", sleep=no_sleep, max_attempts=4)
    assert len(log) == 4


def test_every_retry_is_reported():
    messages = []
    send, _ = fake_sender([429, 503, 200])
    call_with_retry(send, what="TTS unit 3", sleep=no_sleep, on_retry=messages.append)
    assert len(messages) == 2
    assert "TTS unit 3" in messages[0] and "429" in messages[0]


@pytest.mark.parametrize("first", [500, 503, ConnectionError("dropped")])
def test_not_safe_to_repeat_never_retries_ambiguous_failures(first):
    send, log = fake_sender([first, 200])
    with pytest.raises(RequestError):
        call_with_retry(send, what="create job", sleep=no_sleep, safe_to_repeat=False)
    assert len(log) == 1  # did NOT send a second (possibly duplicate, paid) request


def test_not_safe_to_repeat_still_retries_429():
    send, log = fake_sender([429, 200])
    call_with_retry(send, what="create job", sleep=no_sleep, safe_to_repeat=False, on_retry=None)
    assert log == [429, 200]


def test_html_error_pages_are_not_dumped_into_logs():
    messages = []

    def send():
        return SimpleNamespace(status_code=504, text="<!DOCTYPE html>\n<html>...lots of markup...</html>")

    with pytest.raises(RequestError) as e:
        call_with_retry(send, what="QA", sleep=no_sleep, max_attempts=2, on_retry=messages.append)
    assert "HTML error page" in messages[0] and "<html" not in messages[0]
    assert "<html" not in str(e.value)


def test_network_error_is_retried():
    send, log = fake_sender([ConnectionError("dropped"), 200])
    assert call_with_retry(send, what="t", sleep=no_sleep).status_code == 200
