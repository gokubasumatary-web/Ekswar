"""Offline tests for the batch-STT flow with a fake Gnani server. No network, no credits."""

from types import SimpleNamespace

import pytest

from src import gnani
from src.cache import Cache
from src.retry import RequestError


class FakeServer:
    """Pretends to be Gnani: job goes CREATED -> QUEUED -> IN_PROGRESS -> final_status."""

    def __init__(self, final_status="COMPLETED", fail_create=False):
        self.calls = []
        self.statuses = iter(["QUEUED", "IN_PROGRESS", final_status])
        self.final_status = final_status
        self.fail_create = fail_create

    def send(self, method, path, what, **kw):
        self.calls.append((method, path))
        if method == "POST" and path == "/stt/v3/batch/jobs":
            if self.fail_create:
                raise RequestError("boom", 500)
            return SimpleNamespace(json=lambda: {"job_id": "J1", "status": "CREATED"})
        if path.endswith("/start"):
            return SimpleNamespace(json=lambda: {"status": "STARTING"})
        if path.endswith("/files"):
            ok = self.final_status == "COMPLETED"
            return SimpleNamespace(json=lambda: {"data": [{
                "status": "COMPLETED" if ok else "FAILED",
                "transcript_url": "https://s3.example/t.json",
                "error_message": None if ok else "decode error"}]})
        return SimpleNamespace(json=lambda: {"status": next(self.statuses)})


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GNANI_API_KEY", "test-key")
    c = gnani.GnaniClient(cache=Cache(tmp_path / "cache"))
    wav = tmp_path / "v.wav"
    wav.write_bytes(b"RIFF fake audio")
    transcript = {"full_transcript": "नमस्ते", "segments": []}
    monkeypatch.setattr(gnani.requests, "get",
                        lambda url, timeout: SimpleNamespace(status_code=200, text="", json=lambda: transcript))
    return c, wav, transcript


def test_full_flow_then_cache(client):
    c, wav, transcript = client
    server = FakeServer()
    c._send = server.send
    sleeps = []
    assert c.transcribe_batch(wav, sleep=sleeps.append, log=lambda m: None) == transcript
    assert [p for _, p in server.calls][:2] == ["/stt/v3/batch/jobs", "/stt/v3/batch/jobs/J1/start"]
    assert sleeps == [10, 10]  # polled every 10 s, never faster
    n = len(server.calls)
    assert c.transcribe_batch(wav, sleep=sleeps.append, log=lambda m: None) == transcript
    assert len(server.calls) == n  # second time: zero API calls


def test_resume_does_not_create_a_second_job(client):
    c, wav, _ = client
    server = FakeServer()
    c._send = server.send

    def crash(_):
        raise KeyboardInterrupt  # simulate the program dying while waiting

    with pytest.raises(KeyboardInterrupt):
        c.transcribe_batch(wav, sleep=crash, log=lambda m: None)
    c.transcribe_batch(wav, sleep=lambda s: None, log=lambda m: None)
    creates = [p for m, p in server.calls if p == "/stt/v3/batch/jobs" and m == "POST"]
    starts = [p for _, p in server.calls if p.endswith("/start")]
    assert len(creates) == 1 and len(starts) == 1


def test_failed_job_raises_and_is_not_cached(client):
    c, wav, _ = client
    c._send = FakeServer(final_status="FAILED").send
    with pytest.raises(RequestError, match="FAILED"):
        c.transcribe_batch(wav, sleep=lambda s: None, log=lambda m: None)
    assert not list((c.cache.root / "stt_batch").glob("*.json")) if (c.cache.root / "stt_batch").exists() else True


def test_config_uses_documented_model_name():
    assert gnani.batch_config("hi-IN")["model"] == "prisma-v2.5"
