"""The provider side: delivering events to subscribers.

When something happens — a push, an order, a payment — the provider POSTs a
signed JSON payload to every subscribed URL. Deliveries are retried with
exponential backoff because receivers go down: a webhook system without
retries is just wishful thinking.
"""

import asyncio
import json
import logging
import uuid

import httpx

from app import store
from app.config import get_settings
from app.security import sign

logger = logging.getLogger(__name__)

# Overridable factory so tests can deliver via httpx.ASGITransport.
CLIENT_FACTORY = lambda: httpx.AsyncClient(timeout=5, follow_redirects=True)  # noqa: E731


def build_headers(event: dict, delivery_id: str, attempt: int, body: bytes) -> dict:
    """Headers a receiver can expect on every delivery.

    Mirrors GitHub's convention (X-GitHub-Event / X-GitHub-Delivery).
    """
    return {
        "Content-Type": "application/json",
        "X-Webhook-ID": event["id"],          # which event this is
        "X-Webhook-Event": event["type"],      # e.g. "order.created"
        "X-Webhook-Delivery": delivery_id,     # unique per delivery
        "X-Webhook-Attempt": str(attempt),     # retry counter
        "X-Hub-Signature-256": sign(get_settings().webhook_secret, body),
    }


async def deliver(event: dict, url: str, client: httpx.AsyncClient) -> dict:
    """POST one event to one URL, retrying with backoff. Records everything."""
    settings = get_settings()
    delivery_id = uuid.uuid4().hex
    body = json.dumps(event, separators=(",", ":")).encode()
    record = {
        "id": delivery_id,
        "url": url,
        "event_id": event["id"],
        "event": event["type"],
        "status": "delivering",
        "body": body.decode(),
        "attempts": [],
        "started_at": store.now(),
    }
    store.deliveries.append(record)

    for attempt in range(1, settings.max_attempts + 1):
        headers = build_headers(event, delivery_id, attempt, body)
        try:
            resp = await client.post(url, content=body, headers=headers)
            status_code, error = resp.status_code, None
        except httpx.HTTPError as exc:
            status_code, error = None, str(exc)

        record["attempts"].append(
            {
                "n": attempt,
                "at": store.now(),
                "status": status_code,
                "error": error,
                "headers": headers,
            }
        )
        logger.info("delivery %s attempt %d -> %s: %s", delivery_id[:8], attempt, url, status_code or error)

        if status_code is not None and 200 <= status_code < 300:
            record["status"] = "success"
            return record
        if attempt < settings.max_attempts:
            await asyncio.sleep(settings.retry_delay_seconds * 2 ** (attempt - 1))

    record["status"] = "failed"
    return record


async def fan_out(event: dict) -> list[dict]:
    """Deliver one event to every subscriber, in parallel."""
    urls = list(store.subscriptions.values())
    if not urls:
        return []
    async with CLIENT_FACTORY() as client:
        return await asyncio.gather(*(deliver(event, url, client) for url in urls))
