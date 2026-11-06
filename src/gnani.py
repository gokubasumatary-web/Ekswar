"""Client for Gnani APIs (https://api.vachana.ai).

Stage 1, voice cloning:
  - create_voice_embedding(): POST /api/v1/tts/voice-clone/embeddings
  - synthesize_cloned():      POST /api/v1/tts/inference  (model vachana-vc-v1)
Stage 3, Prisma batch speech-to-text:
  - transcribe_batch(): POST /stt/v3/batch/jobs -> POST .../{id}/start ->
    GET .../{id} (poll >= 10 s) -> GET .../{id}/files -> GET transcript_url

Endpoints and fields follow docs.gnani.ai (read 2026-11-06). Every call goes
through the disk cache (no repeat charges) and the retry rules in retry.py.
The API key is only ever placed in the request header, never logged.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

import requests

from .cache import Cache, file_hash, make_key
from .config import CACHE_DIR, GNANI_BASE_URL, get_setting
from .retry import RequestError, call_with_retry

VC_MODEL = "vachana-vc-v1"
DEFAULT_AUDIO_CONFIG = {"sample_rate": 44100, "encoding": "linear_pcm", "container": "wav"}
NETWORK_ERRORS = (requests.ConnectionError, requests.Timeout)

STT_MODEL = "prisma-v2.5"  # docs (live-verified example); brief said "gnani-prisma-v2.5"
BATCH_POLL_SECONDS = 10    # docs: poll no more often than every 10 s
BATCH_TERMINAL = {"COMPLETED", "PARTIAL_FAILURE", "FAILED", "START_FAILED", "CANCELLED"}


def batch_config(language_code: str) -> dict:
    return {"model": STT_MODEL, "language_code": language_code, "mode": "transcribe",
            "with_diarization": False, "is_multi_channel": False}


# --------------------------------------------------------------------------
# Pure helpers (tested offline)
# --------------------------------------------------------------------------

def parse_embedding_response(body: Any) -> dict:
    """Extract {embedding, shape, dtype} from the embeddings response.

    Docs show it wrapped in data.voice_clone_embedding; the brief says it may
    also come back unwrapped. Accept both, reject anything else loudly.
    """
    candidates = []
    if isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, dict) and isinstance(data.get("voice_clone_embedding"), dict):
            candidates.append(data["voice_clone_embedding"])
        candidates.append(body)
    for c in candidates:
        if all(k in c for k in ("embedding", "shape", "dtype")) and isinstance(c["embedding"], str):
            return {"embedding": c["embedding"], "shape": list(c["shape"]), "dtype": c["dtype"]}
    keys = list(body.keys()) if isinstance(body, dict) else type(body).__name__
    raise RequestError(f"Unexpected embedding response shape (top-level keys: {keys})")


def check_wav_bytes(data: bytes, content_type: str) -> bytes:
    """Make sure a 200 TTS response really is WAV audio, not a JSON error."""
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return data
    preview = data[:300].decode("utf-8", errors="replace")
    raise RequestError(f"TTS returned non-WAV data (Content-Type {content_type!r}): {preview}")


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------

class GnaniClient:
    def __init__(self, cache: Cache | None = None, timeout: float = 120.0):
        self.cache = cache or Cache(CACHE_DIR)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["X-API-Key-ID"] = get_setting("GNANI_API_KEY")
        self.api_calls = 0  # real (non-cached) calls, for the metrics report

    def _send(self, method: str, path: str, what: str, *, safe_to_repeat: bool = True,
              **kwargs) -> requests.Response:
        def send():
            self.api_calls += 1
            return self.session.request(method, GNANI_BASE_URL + path, timeout=self.timeout, **kwargs)
        return call_with_retry(send, what=what, network_errors=NETWORK_ERRORS,
                               safe_to_repeat=safe_to_repeat)

    # -- voice cloning -------------------------------------------------------
    def create_voice_embedding(self, ref_audio: str | Path) -> dict:
        """Turn a 5-30 s reference recording into a speaker embedding (cached)."""
        ref_audio = Path(ref_audio)
        key = make_key("vc-embedding-v1", file_hash(ref_audio))

        def compute():
            with open(ref_audio, "rb") as f:
                files = {"audio_file": (ref_audio.name, f, _mime_for(ref_audio))}
                resp = self._send("POST", "/api/v1/tts/voice-clone/embeddings", "voice embedding", files=files)
            return {"raw_top_level_keys": sorted(resp.json().keys()),
                    "speaker_embedding": parse_embedding_response(resp.json())}

        return self.cache.json_or_compute("embedding", key, compute)["speaker_embedding"]

    def synthesize_cloned(self, text: str, speaker_embedding: dict,
                          audio_config: dict | None = None, what: str = "cloned TTS") -> bytes:
        """Speak `text` in the cloned voice. Returns WAV bytes (cached)."""
        audio_config = audio_config or DEFAULT_AUDIO_CONFIG
        payload = {"text": text, "model": VC_MODEL, "audio_config": audio_config,
                   "speaker_embedding": speaker_embedding}
        key = make_key("vc-tts-v1", VC_MODEL, text, audio_config, speaker_embedding)

        def compute():
            resp = self._send("POST", "/api/v1/tts/inference", what, json=payload)
            return check_wav_bytes(resp.content, resp.headers.get("Content-Type", ""))

        return self.cache.bytes_or_compute("tts", key, "wav", compute)

    # -- Prisma batch speech-to-text ------------------------------------------
    def transcribe_batch(self, wav: str | Path, language_code: str = "hi-IN", *,
                         max_wait_seconds: float = 900,
                         sleep: Callable[[float], None] = time.sleep,
                         log: Callable[[str], None] = print) -> dict:
        """Transcribe a 16 kHz mono WAV with Prisma v2.5 batch. Returns the raw transcript JSON.

        Credit safety: the job id is saved right after creation, so if this crashes
        while waiting, the next call resumes the SAME job instead of paying for a new one.
        """
        wav = Path(wav)
        config = batch_config(language_code)
        key = make_key("stt-batch-v1", file_hash(wav), config)
        cached = self.cache.get_json("stt_batch", key)
        if cached is not None:
            return cached

        job = self.cache.get_json("stt_batch_job", key)
        if job is None:
            with open(wav, "rb") as f:
                files = {"config": (None, json.dumps(config), "application/json"),
                         "files": (wav.name, f, "audio/wav")}
                resp = self._send("POST", "/stt/v3/batch/jobs", "batch STT create",
                                  safe_to_repeat=False, files=files)
            job = {"job_id": resp.json()["job_id"], "started": False, "create_response": resp.json()}
            self.cache.put_json("stt_batch_job", key, job)
            log(f"  job created: {job['job_id']}")
        else:
            log(f"  resuming saved job: {job['job_id']}")

        job_id = job["job_id"]
        if not job["started"]:
            self._send("POST", f"/stt/v3/batch/jobs/{job_id}/start", "batch STT start")
            job["started"] = True
            self.cache.put_json("stt_batch_job", key, job)
            log("  job started")

        waited, status = 0.0, None
        while True:
            body = self._send("GET", f"/stt/v3/batch/jobs/{job_id}", "batch STT status").json()
            status = body.get("status")
            log(f"  status: {status} ({waited:.0f} s)")
            if status in BATCH_TERMINAL:
                if status != "COMPLETED" and body.get("cancel_reason"):
                    log(f"  cancel_reason: {body['cancel_reason']}")
                break
            if waited >= max_wait_seconds:
                raise RequestError(f"batch STT job {job_id} still {status} after {waited:.0f} s "
                                   f"(job saved; re-run to keep waiting)")
            sleep(BATCH_POLL_SECONDS)
            waited += BATCH_POLL_SECONDS

        files_body = self._send("GET", f"/stt/v3/batch/jobs/{job_id}/files",
                                "batch STT files").json()  # no status filter: see failures too
        entries = files_body.get("data") or []
        if status != "COMPLETED" or not entries or entries[0].get("status") != "COMPLETED":
            detail = [(e.get("status"), e.get("error_message")) for e in entries]
            raise RequestError(f"batch STT job {job_id} ended {status}; files: {detail}")

        # Pre-signed S3 link: plain GET, deliberately WITHOUT our API key header.
        url = entries[0]["transcript_url"]
        dl = call_with_retry(lambda: requests.get(url, timeout=self.timeout),
                             what="batch STT download", network_errors=NETWORK_ERRORS)
        transcript = dl.json()
        self.cache.put_json("stt_batch", key, transcript)
        return transcript


def _mime_for(path: Path) -> str:
    return {".wav": "audio/wav", ".mp3": "audio/mpeg"}.get(path.suffix.lower(), "application/octet-stream")
