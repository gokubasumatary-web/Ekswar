"""Retry rules for HTTP API calls (Gnani now, reusable elsewhere).

What each HTTP status means for us (from docs.gnani.ai, 2026-11-06):

  2xx            success, return the response
  429, 503, 504  temporary (rate limit / unavailable / timeout): wait and retry,
                 waiting longer each time (2 s, 4 s, 8 s, ...). 429 sends no
                 Retry-After header, so we choose the wait ourselves.
  500            unexpected error; can also mean "text too long". Retry ONCE only.
  400, 422, etc. our request is wrong: no retry, raise RequestError.
  401, 402, 403  bad key / no credit / no permission: raise FatalAPIError so the
                 whole run stops. Retrying can't fix these.
  network error  (connection dropped, timeout): treated like 503.

The function takes `send` (makes one HTTP request) and `sleep` as parameters,
so tests can use fakes without touching the network.
"""

from __future__ import annotations

import time
from typing import Any, Callable

RETRY_FOREVER_ISH = {429, 503, 504}
RETRY_ONCE = {500}
FATAL = {401, 402, 403}


class APIError(Exception):
    def __init__(self, message: str, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


class RequestError(APIError):
    """This request failed and retrying won't help. The unit fails; the run continues."""


class FatalAPIError(APIError):
    """Key, credit or permission problem. The whole run must stop."""


def _short(text: str, limit: int = 500) -> str:
    """Shorten an error body for logs. Gateways sometimes return a whole HTML page (e.g. a 504)."""
    if text.lstrip().lower().startswith(("<!doctype html", "<html")):
        return "(HTML error page from a gateway/proxy, not a JSON API error)"
    return text if len(text) <= limit else text[:limit] + "..."


def call_with_retry(
    send: Callable[[], Any],
    *,
    what: str,
    max_attempts: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
    network_errors: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError),
    on_retry: Callable[[str], None] | None = print,
    safe_to_repeat: bool = True,
    give_up_if: Callable[[Any], bool] | None = None,
) -> Any:
    """Call `send()` until it succeeds or a rule says stop. Returns the response.

    `send` must return an object with `.status_code` and `.text` (e.g. requests.Response).
    `what` is a short label for error messages, e.g. "TTS unit 3".
    `on_retry` is told about every retry (never silent). Pass None to mute in tests.
    `safe_to_repeat=False` is for requests that create something paid (e.g. a batch
    job): after a network error or 5xx the server MAY have done it already, so only
    429 (definitely rejected) is retried; everything else raises.
    `give_up_if(resp)` -> True means "retrying cannot help" (e.g. a DAILY quota is used up):
    raise immediately instead of waiting and retrying.
    """
    attempt = 0
    used_500_retry = False

    def wait(seconds: float, reason: str) -> None:
        if on_retry:
            on_retry(f"  [retry] {what}: {reason}; waiting {seconds:.0f} s (attempt {attempt}/{max_attempts})")
        sleep(seconds)

    while True:
        attempt += 1
        try:
            resp = send()
        except network_errors as e:
            if not safe_to_repeat:
                raise RequestError(f"{what}: network error ({e}); not retried because the server "
                                   f"may have already done it. Check before re-running.") from e
            if attempt >= max_attempts:
                raise RequestError(f"{what}: network error after {attempt} attempts: {e}") from e
            wait(min(base_delay * 2 ** (attempt - 1), max_delay), f"network error {type(e).__name__}")
            continue

        status = resp.status_code
        if 200 <= status < 300:
            return resp

        body = _short(getattr(resp, "text", "") or "")
        if status in FATAL:
            raise FatalAPIError(f"{what}: HTTP {status} (key, credit or permission problem): {body}", status, body)
        if give_up_if is not None and give_up_if(resp):
            raise RequestError(f"{what}: HTTP {status}, not retried (retrying cannot help): {body}", status, body)
        if not safe_to_repeat and status != 429:
            raise RequestError(f"{what}: HTTP {status}, not retried (may have been created): {body}", status, body)
        if status in RETRY_ONCE and not used_500_retry and attempt < max_attempts:
            used_500_retry = True
            wait(base_delay, f"HTTP {status} {body[:120]}")
            continue
        if status in RETRY_FOREVER_ISH and attempt < max_attempts:
            wait(min(base_delay * 2 ** (attempt - 1), max_delay), f"HTTP {status} {body[:120]}")
            continue
        raise RequestError(f"{what}: HTTP {status} after {attempt} attempt(s): {body}", status, body)
