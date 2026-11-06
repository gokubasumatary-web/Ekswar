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
) -> Any:
    """Call `send()` until it succeeds or a rule says stop. Returns the response.

    `send` must return an object with `.status_code` and `.text` (e.g. requests.Response).
    `what` is a short label for error messages, e.g. "TTS unit 3".
    """
    attempt = 0
    used_500_retry = False
    while True:
        attempt += 1
        try:
            resp = send()
        except network_errors as e:
            if attempt >= max_attempts:
                raise RequestError(f"{what}: network error after {attempt} attempts: {e}") from e
            sleep(min(base_delay * 2 ** (attempt - 1), max_delay))
            continue

        status = resp.status_code
        if 200 <= status < 300:
            return resp

        body = _short(getattr(resp, "text", "") or "")
        if status in FATAL:
            raise FatalAPIError(f"{what}: HTTP {status} (key, credit or permission problem): {body}", status, body)
        if status in RETRY_ONCE and not used_500_retry and attempt < max_attempts:
            used_500_retry = True
            sleep(base_delay)
            continue
        if status in RETRY_FOREVER_ISH and attempt < max_attempts:
            sleep(min(base_delay * 2 ** (attempt - 1), max_delay))
            continue
        raise RequestError(f"{what}: HTTP {status} after {attempt} attempt(s): {body}", status, body)
