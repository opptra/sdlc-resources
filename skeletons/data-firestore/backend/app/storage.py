"""Cloud Storage helper with report freshness check."""

from __future__ import annotations

import time


class InMemoryBucket:
    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, float]] = {}

    def write_bytes(self, path: str, content: bytes, created_at: float | None = None) -> None:
        self._objects[path] = (content, created_at if created_at is not None else time.time())

    def read_fresh(self, path: str, max_age_seconds: int = 7200, now: float | None = None) -> bytes:
        if path not in self._objects:
            raise FileNotFoundError(path)
        content, created_at = self._objects[path]
        current = now if now is not None else time.time()
        if current - created_at > max_age_seconds:
            raise TimeoutError(f"{path} is older than {max_age_seconds}s")
        return content
