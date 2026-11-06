"""The ONE place Ekswar talks to an LLM (Gemini). Swap providers by changing only this file.

Used for: punctuation + merging (Stage 5), translation (Stage 6), shortening (Stage 7).

    ask_json(prompt, schema=None) -> dict | list

How it works (Gemini REST generateContent, docs read 2026-11-07):
  POST https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent
  header x-goog-api-key, body {contents, generationConfig}
  generationConfig.responseMimeType = "application/json"   (reply must be JSON)
  generationConfig.responseJsonSchema = schema              (optional exact shape)
  generationConfig.thinkingConfig.thinkingLevel = "LOW"     (Gemini 3: faster, enough for translation)
  No temperature: ignored on Gemini 3.6+ models.

Safety: every reply is cached by (model + prompt + schema + settings), so the same
question is never asked twice. Retries follow retry.py; a missing model (404) or
blocked key (403) stops the run.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable

import requests

from .cache import Cache, make_key
from .config import CACHE_DIR, get_setting
from .retry import FatalAPIError, RequestError, call_with_retry

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
THINKING_LEVEL = "LOW"
NETWORK_ERRORS = (requests.ConnectionError, requests.Timeout)
STRICT_SUFFIX = "\n\nIMPORTANT: Reply with ONLY valid JSON. No explanations, no markdown fences."

# Backup model (optional env GEMINI_FALLBACK_MODEL): used only when the main model
# is busy/unreachable (429, 5xx, timeouts), never for blocked prompts or bad JSON.
BUSY_STATUSES = {429, 500, 503, 504}
PRIMARY_ATTEMPTS_WITH_FALLBACK = 3
PRIMARY_TIMEOUT_WITH_FALLBACK = 45.0


class ModelUnavailable(RequestError):
    """The model stayed busy or unreachable after its retries."""


# --------------------------------------------------------------------------
# Pure helpers (tested offline)
# --------------------------------------------------------------------------

def build_body(prompt: str, schema: dict | None) -> dict:
    gen: dict[str, Any] = {"responseMimeType": "application/json",
                           "thinkingConfig": {"thinkingLevel": THINKING_LEVEL}}
    if schema is not None:
        gen["responseJsonSchema"] = schema
    return {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen}


def extract_text(body: dict) -> str:
    """Pull the answer text out of a generateContent response, or explain why there is none."""
    block = (body.get("promptFeedback") or {}).get("blockReason")
    if block:
        raise RequestError(f"Gemini blocked the prompt ({block})")
    candidates = body.get("candidates") or []
    if not candidates:
        raise RequestError("Gemini returned no candidates")
    cand = candidates[0]
    reason = cand.get("finishReason", "STOP")
    parts = (cand.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if reason != "STOP":
        raise RequestError(f"Gemini stopped early (finishReason={reason}); partial text: {text[:200]!r}")
    if not text.strip():
        raise RequestError("Gemini returned an empty answer")
    return text


def parse_json_text(text: str) -> Any:
    """json.loads, tolerating a ```json fence if the model adds one anyway."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    return json.loads(t)


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------

class LLM:
    def __init__(self, cache: Cache | None = None, timeout: float = 60.0,
                 on_retry: Callable[[str], None] | None = print, log: Callable[[str], None] = print):
        self.cache = cache or Cache(CACHE_DIR)
        self.model = get_setting("GEMINI_MODEL")
        self.fallback_model = os.environ.get("GEMINI_FALLBACK_MODEL", "").strip() or None
        self.timeout = timeout
        self.on_retry = on_retry
        self.log = log
        self.session = requests.Session()
        self.session.headers["x-goog-api-key"] = get_setting("GEMINI_API_KEY")
        self.api_calls = 0
        self.fallback_used = 0  # how many answers came from the backup model
        self.sleep = time.sleep  # replaceable in tests

    def _post(self, model: str, body: dict, what: str, *, attempts: int, timeout: float) -> dict:
        url = f"{API_BASE}/{model}:generateContent"

        def send():
            self.api_calls += 1
            return self.session.post(url, json=body, timeout=timeout)

        try:
            resp = call_with_retry(send, what=f"{what} [{model}]", network_errors=NETWORK_ERRORS,
                                   max_attempts=attempts, max_delay=60, on_retry=self.on_retry,
                                   sleep=self.sleep)
        except RequestError as e:
            if e.status == 404:  # wrong model name: every call would fail, so stop the run
                raise FatalAPIError(f"{what}: model '{model}' not found (check GEMINI_MODEL / "
                                    f"GEMINI_FALLBACK_MODEL). {e.body}", 404, e.body) from e
            if e.status is None or e.status in BUSY_STATUSES:
                raise ModelUnavailable(str(e), e.status, e.body) from e
            raise
        return resp.json()

    def _ask_one_model(self, model: str, prompt: str, schema: dict | None, what: str,
                       *, attempts: int, timeout: float) -> Any:
        text = extract_text(self._post(model, build_body(prompt, schema), what,
                                       attempts=attempts, timeout=timeout))
        try:
            return parse_json_text(text)
        except json.JSONDecodeError:
            # one stricter re-ask, then give up on this item
            strict = build_body(prompt + STRICT_SUFFIX, schema)
            text2 = extract_text(self._post(model, strict, what + " (strict re-ask)",
                                            attempts=attempts, timeout=timeout))
            try:
                return parse_json_text(text2)
            except json.JSONDecodeError as e:
                raise RequestError(f"{what}: Gemini did not return valid JSON twice: {text2[:200]!r}") from e

    def ask_json(self, prompt: str, schema: dict | None = None, what: str = "LLM") -> Any:
        """Ask Gemini; return the parsed JSON answer. Cached per model.

        With GEMINI_FALLBACK_MODEL set: the main model gets fewer retries and a
        shorter timeout; if it stays busy/unreachable, the backup model is asked.
        """
        body = build_body(prompt, schema)
        models = [self.model] + ([self.fallback_model] if self.fallback_model else [])
        keys = {m: make_key("gemini-json-v1", m, body) for m in models}

        for m in models:  # any cached answer (from either model) is reused: 0 calls
            hit = self.cache.get_json("llm", keys[m])
            if hit is not None:
                return hit["answer"]

        if self.fallback_model:
            try:
                answer = self._ask_one_model(self.model, prompt, schema, what,
                                             attempts=PRIMARY_ATTEMPTS_WITH_FALLBACK,
                                             timeout=PRIMARY_TIMEOUT_WITH_FALLBACK)
                model_used = self.model
            except ModelUnavailable as e:
                self.log(f"  [fallback] {what}: {self.model} unavailable ({str(e)[:100]}); "
                         f"asking {self.fallback_model}")
                answer = self._ask_one_model(self.fallback_model, prompt, schema, what,
                                             attempts=6, timeout=self.timeout)
                model_used = self.fallback_model
                self.fallback_used += 1
        else:
            answer = self._ask_one_model(self.model, prompt, schema, what, attempts=6, timeout=self.timeout)
            model_used = self.model

        self.cache.put_json("llm", keys[model_used], {"answer": answer, "model": model_used})
        return answer


if __name__ == "__main__":
    # Quick live check:  python -m src.llm
    llm = LLM()
    schema = {"type": "object", "properties": {"ta": {"type": "string"}}, "required": ["ta"]}
    ans = llm.ask_json("Translate 'नमस्ते दोस्तों' (Hindi) into Tamil. Return JSON {\"ta\": ...}.",
                       schema, what="llm smoke test")
    print(json.dumps(ans, ensure_ascii=False),
          f"| model={llm.model} fallback={llm.fallback_model} real calls={llm.api_calls} "
          f"fallback used={llm.fallback_used}")
