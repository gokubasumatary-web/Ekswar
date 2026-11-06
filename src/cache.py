"""Disk cache for API results.

Why: Gnani credits are limited (5,000), so the same request must never be paid
for twice. Every API result is saved under cache/<kind>/<key>.<ext>, where
<key> is a SHA-256 hash of everything that affects the result.

Rules:
- Only successful results are stored, never errors.
- Files are written atomically (temp file, then rename), so a crash never
  leaves a half-written file that looks like a valid result.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable


def make_key(*parts: Any) -> str:
    """Build a stable hash from request inputs (strings, numbers, dicts, lists, bytes).

    The same inputs always give the same key; any change gives a different key.
    """
    h = hashlib.sha256()
    for part in parts:
        if isinstance(part, (bytes, bytearray)):
            h.update(b"B")
            h.update(hashlib.sha256(part).digest())
        else:
            h.update(b"J")
            h.update(json.dumps(part, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def file_hash(path: str | Path) -> str:
    """SHA-256 of a file's contents (used to key uploads such as audio files)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Cache:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.hits = 0
        self.misses = 0

    def path(self, kind: str, key: str, ext: str) -> Path:
        return self.root / kind / f"{key}.{ext}"

    # --- raw bytes (audio clips) -------------------------------------------
    def get_bytes(self, kind: str, key: str, ext: str) -> bytes | None:
        p = self.path(kind, key, ext)
        if p.exists():
            self.hits += 1
            return p.read_bytes()
        self.misses += 1
        return None

    def put_bytes(self, kind: str, key: str, ext: str, data: bytes) -> Path:
        p = self.path(kind, key, ext)
        _atomic_write(p, data)
        return p

    # --- JSON (transcripts, embeddings, LLM replies) -----------------------
    def get_json(self, kind: str, key: str) -> Any | None:
        raw = self.get_bytes(kind, key, "json")
        return None if raw is None else json.loads(raw.decode("utf-8"))

    def put_json(self, kind: str, key: str, value: Any) -> Path:
        data = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
        return self.put_bytes(kind, key, "json", data)

    # --- convenience: return cached value, or compute + store it -----------
    def json_or_compute(self, kind: str, key: str, compute: Callable[[], Any]) -> Any:
        cached = self.get_json(kind, key)
        if cached is not None:
            return cached
        value = compute()  # if this raises, nothing is stored
        self.put_json(kind, key, value)
        return value

    def bytes_or_compute(self, kind: str, key: str, ext: str, compute: Callable[[], bytes]) -> bytes:
        cached = self.get_bytes(kind, key, ext)
        if cached is not None:
            return cached
        value = compute()
        self.put_bytes(kind, key, ext, value)
        return value


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
