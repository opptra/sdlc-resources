"""Firestore state helpers: lease locks, heartbeats, idempotency keys, and master pointers."""

from __future__ import annotations

import time
from typing import Protocol


class StateBackend(Protocol):
    def get_doc(self, collection: str, doc_id: str) -> dict | None: ...
    def set_doc(self, collection: str, doc_id: str, data: dict) -> None: ...


class InMemoryStateBackend:
    """In-memory Firestore fake for local runs and unit tests."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], dict] = {}

    def get_doc(self, collection: str, doc_id: str) -> dict | None:
        doc = self._store.get((collection, str(doc_id)))
        return dict(doc) if doc is not None else None

    def set_doc(self, collection: str, doc_id: str, data: dict) -> None:
        self._store[(collection, str(doc_id))] = dict(data)


class FirestoreState:
    def __init__(self, backend: StateBackend | None = None) -> None:
        self.backend: StateBackend = backend or InMemoryStateBackend()

    def acquire_lease(
        self, job_name: str, ttl_seconds: int = 1800, now: float | None = None
    ) -> bool:
        ts = now if now is not None else time.time()
        existing = self.backend.get_doc("locks", job_name)
        if existing and float(existing.get("expires_at", 0)) > ts:
            return False
        self.backend.set_doc("locks", job_name, {"job": job_name, "expires_at": ts + ttl_seconds})
        return True

    def release_lease(self, job_name: str) -> None:
        self.backend.set_doc("locks", job_name, {"job": job_name, "expires_at": 0})

    def record_heartbeat(self, job_name: str, run_id: str, now: float | None = None) -> None:
        ts = now if now is not None else time.time()
        self.backend.set_doc(
            "heartbeats", job_name, {"job": job_name, "last_success": ts, "run_id": run_id}
        )

    def is_processed(self, job_name: str, item_id: str | int) -> bool:
        return self.backend.get_doc(f"processed/{job_name}/items", str(item_id)) is not None

    def mark_processed(
        self, job_name: str, item_id: str | int, metadata: dict | None = None
    ) -> None:
        payload = {"item_id": str(item_id), "processed_at": time.time()}
        if metadata:
            payload.update(metadata)
        self.backend.set_doc(f"processed/{job_name}/items", str(item_id), payload)

    def get_masters_generation(self) -> str | None:
        meta = self.backend.get_doc("meta", "masters")
        return str(meta["generation"]) if meta and "generation" in meta else None

    def set_masters_generation(self, generation: str) -> None:
        self.backend.set_doc(
            "meta", "masters", {"generation": generation, "updated_at": time.time()}
        )
