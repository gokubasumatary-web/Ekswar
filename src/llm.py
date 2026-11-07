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

# Backup models (optional env GEMINI_FALLBACK_MODEL, comma-separated, tried in order):
# used only when a model is busy/unreachable (429, 5xx, timeouts), never for blocked
# prompts or bad JSON. Every model except the last gets fewer tries and a shorter timeout.
BUSY_STATUSES = {429, 500, 503, 504}
PRIMARY_ATTEMPTS_WITH_FALLBACK = 3
PRIMARY_TIMEOUT_WITH_FALLBACK = 45.0


class ModelUnavailable(RequestError):
    """The model stayed busy or unreachable after its retries."""


def is_quota_exhausted(resp) -> bool:
    """A 429 'You exceeded your current quota' (free-tier quota hit). Retrying the SAME
    model right away cannot help, so switch model. It can be a per-minute OR per-day
    quota; quota_info() tells which (seen 2026-11-07: the same message for both)."""
    if resp.status_code != 429:
        return False
    text = (getattr(resp, "text", "") or "").lower()
    return "exceeded your current quota" in text or "quota exceeded" in text


DEFAULT_COOLDOWN = 60.0


def quota_info(text: str) -> tuple[bool, float, str]:
    """(is_daily, cooldown_seconds, quota_ids) from a Gemini 429 body.

    Google errors usually carry details: QuotaFailure.violations[].quotaId (e.g. names
    containing 'PerDay' or 'PerMinute') and RetryInfo.retryDelay (e.g. '38s'). Read
    defensively: if unknown, assume per-minute with a 60 s cool-down (safer than
    giving up on a model for the whole day). NOT yet verified against a real body.
    """
    ids, delay = [], None
    try:
        details = json.loads(text).get("error", {}).get("details", []) or []
    except (ValueError, AttributeError):
        details = []
    for d in details:
        for v in d.get("violations", []) or []:
            if v.get("quotaId"):
                ids.append(str(v["quotaId"]))
        rd = d.get("retryDelay")
        if isinstance(rd, str) and rd.endswith("s"):
            try:
                delay = float(rd[:-1])
            except ValueError:
                pass
    joined = ",".join(ids)
    is_daily = "perday" in joined.lower()
    return is_daily, min(max(delay or DEFAULT_COOLDOWN, 1.0), 120.0), joined


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
        self.fallback_models = [m.strip() for m in os.environ.get("GEMINI_FALLBACK_MODEL", "").split(",")
                                if m.strip() and m.strip() != self.model]
        self.fallback_model = ", ".join(self.fallback_models) or None  # for display
        self.exhausted: set[str] = set()      # models whose DAILY quota ran out during this run
        self.cooldown: dict[str, float] = {}  # model -> time.time() when it may be used again
        self.clock = time.time                # replaceable in tests
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

        quota_hit = []

        def give_up(resp) -> bool:
            if is_quota_exhausted(resp):
                quota_hit.append(quota_info(getattr(resp, "text", "") or ""))
                return True
            return False

        try:
            resp = call_with_retry(send, what=f"{what} [{model}]", network_errors=NETWORK_ERRORS,
                                   max_attempts=attempts, max_delay=60, on_retry=self.on_retry,
                                   sleep=self.sleep, give_up_if=give_up)
        except RequestError as e:
            if e.status == 404:  # wrong model name: every call would fail, so stop the run
                raise FatalAPIError(f"{what}: model '{model}' not found (check GEMINI_MODEL / "
                                    f"GEMINI_FALLBACK_MODEL). {e.body}", 404, e.body) from e
            if quota_hit:
                is_daily, cool, ids = quota_hit[0]
                if is_daily:
                    self.exhausted.add(model)
                    self.log(f"  [quota] {model}: DAILY quota used up ({ids}); skipping it for this run")
                else:
                    self.cooldown[model] = self.clock() + cool
                    self.log(f"  [quota] {model}: quota hit ({ids or 'details not given'}); "
                             f"pausing it for {cool:.0f} s")
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

    def ask_json(self, prompt: str, schema: dict | None = None, what: str = "LLM",
                 validate: Callable[[Any], bool] | None = None) -> Any:
        """Ask Gemini; return the parsed JSON answer. Cached per model.

        Models are tried in order: GEMINI_MODEL, then each GEMINI_FALLBACK_MODEL. All but
        the last get fewer retries and a shorter timeout. A model whose daily quota ran
        out is skipped for the rest of the run (no wasted calls).

        validate(answer) -> False means "wrong answer" (e.g. wrong script): it is NOT
        cached and the next model is tried; if no model gives a valid answer, the last
        invalid one is returned (uncached) so the caller can flag it.
        """
        body = build_body(prompt, schema)
        models = [self.model] + self.fallback_models
        keys = {m: make_key("gemini-json-v1", m, body) for m in models}

        for m in models:  # a cached answer (from any model) is reused: 0 calls
            hit = self.cache.get_json("llm", keys[m])
            if hit is not None and (validate is None or validate(hit["answer"])):
                return hit["answer"]  # (old cached answers that fail `validate` are ignored)

        last_error: ModelUnavailable | None = None
        invalid_answer, tried_invalid = None, set()
        for round_no in (1, 2):  # round 2 only if a model was paused by a per-minute quota
            alive = [m for m in models if m not in self.exhausted and m not in tried_invalid]
            if not alive:
                break
            now = self.clock()
            candidates = [m for m in alive if self.cooldown.get(m, 0) <= now]
            if not candidates:  # all paused by per-minute quotas: wait for the first one to be free
                first = min(alive, key=lambda m: self.cooldown[m])
                wait = self.cooldown[first] - now
                self.log(f"  [quota] all models paused; waiting {wait:.0f} s for {first}")
                self.sleep(wait)
                candidates = [first]
            for i, m in enumerate(candidates):
                is_last = i == len(candidates) - 1
                if i > 0 or round_no > 1:
                    self.log(f"  [fallback] {what}: asking {m} ({str(last_error or 'invalid answer')[:100]})")
                try:
                    answer = self._ask_one_model(
                        m, prompt, schema, what,
                        attempts=6 if is_last else PRIMARY_ATTEMPTS_WITH_FALLBACK,
                        timeout=self.timeout if is_last else PRIMARY_TIMEOUT_WITH_FALLBACK)
                except ModelUnavailable as e:
                    last_error = e
                    continue
                if validate is not None and not validate(answer):
                    self.log(f"  [invalid] {what}: answer from {m} failed validation; trying the next model")
                    invalid_answer = answer
                    tried_invalid.add(m)
                    continue
                if m != self.model:
                    self.fallback_used += 1
                self.cache.put_json("llm", keys[m], {"answer": answer, "model": m})
                return answer
            paused = [m for m in models if m not in self.exhausted and m not in tried_invalid
                      and self.cooldown.get(m, 0) > self.clock()]
            if not paused:
                break
        if invalid_answer is not None:
            return invalid_answer  # NOT cached: the caller's own checks will flag it
        if not any(m not in self.exhausted for m in models):
            raise ModelUnavailable(f"{what}: every Gemini model's daily quota is used up "
                                   f"({', '.join(models)}); try again after the daily reset")
        raise last_error or ModelUnavailable(f"{what}: no model answered")


if __name__ == "__main__":
    # Quick live check:  python -m src.llm
    llm = LLM()
    schema = {"type": "object", "properties": {"ta": {"type": "string"}}, "required": ["ta"]}
    ans = llm.ask_json("Translate 'नमस्ते दोस्तों' (Hindi) into Tamil. Return JSON {\"ta\": ...}.",
                       schema, what="llm smoke test")
    print(json.dumps(ans, ensure_ascii=False),
          f"| model={llm.model} fallback={llm.fallback_model} real calls={llm.api_calls} "
          f"fallback used={llm.fallback_used}")
