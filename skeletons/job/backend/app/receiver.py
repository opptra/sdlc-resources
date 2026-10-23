"""Webhook receiver that verifies a shared secret header and enqueues work."""

from __future__ import annotations

import hmac
import os
from collections.abc import Callable

from app.logging import configure_logging

configure_logging()


def verify_webhook_secret(header_value: str | None, expected_secret: str | None = None) -> bool:
    env_secret = os.environ.get("WEBHOOK_SECRET", "")
    expected = expected_secret if expected_secret is not None else env_secret
    if not expected or not header_value:
        return False
    return hmac.compare_digest(header_value, expected)


def handle_webhook(
    payload: dict,
    secret_header: str | None,
    expected_secret: str | None = None,
    enqueue: Callable[[dict], None] | None = None,
) -> tuple[int, dict]:
    if not verify_webhook_secret(secret_header, expected_secret):
        return 401, {"error": "unauthorized"}
    ticket_id = payload.get("ticket_id")
    if ticket_id is None:
        return 400, {"error": "missing ticket_id"}
    task_body = {"ticket_id": ticket_id, "trigger": "webhook"}
    if enqueue is not None:
        enqueue(task_body)
    return 200, {"status": "queued", "ticket_id": ticket_id}
