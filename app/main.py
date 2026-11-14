"""A self-contained webhook playground — both sides of the lifecycle in one app.

Run:  uv run uvicorn app.main:app --reload
Then: uv run python scripts/demo.py

PROVIDER side (we send webhooks, like GitHub/Stripe do):
  POST /subscriptions     register a callback URL
  GET  /subscriptions     list them
  POST /emit              fire an event -> delivered to every subscriber
  GET  /deliveries        delivery log, including every retry attempt

RECEIVER side (we receive webhooks, like your app would):
  POST /webhooks/receive  verify signature, dedupe, record the event
  POST /webhooks/flaky    500s twice, then succeeds — watch retries happen
  POST /webhooks/dead     always 500s — watch a delivery exhaust its retries
  GET  /events            everything we've received

Plus GET / — an interactive dashboard that walks through the lifecycle
(subscribe → emit → deliver/retry → verify/dedupe), fed by GET /state.
"""

import json
import logging
import uuid

from pathlib import Path
from typing import Literal

import httpx

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import store
from app.config import get_settings
from app.dispatcher import fan_out
from app.security import sign, verify

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="webhooks-101",
    version="0.1.0",
    description="A minimal playground that is both a webhook provider and receiver.",
)


class SubscribeRequest(BaseModel):
    url: str


class EmitRequest(BaseModel):
    type: str = "demo.ping"
    data: dict = {}


# ---------------------------------------------------------------- receiver


@app.post("/webhooks/receive")
async def receive(request: Request) -> dict:
    """The endpoint you'd point GitHub, Stripe, or this very app at."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify(get_settings().webhook_secret, body, signature):
        # 401, not 400: from the sender's view the request is unauthenticated.
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload must be JSON") from None

    # Our dispatcher sends X-Webhook-*; real providers send their own flavor
    # (X-GitHub-Event, X-GitHub-Delivery). Accept both so real GitHub
    # webhooks verify and record here unchanged.
    event_type = (
        request.headers.get("X-Webhook-Event")
        or request.headers.get("X-GitHub-Event")
        or (payload.get("type") if isinstance(payload, dict) else None)
        or "unknown"
    )
    delivery_id = request.headers.get("X-Webhook-Delivery") or request.headers.get(
        "X-GitHub-Delivery"
    )

    # Idempotency: webhooks are at-least-once — retries and provider quirks
    # mean the same delivery can arrive twice. Receivers dedupe on the
    # delivery ID.
    duplicate = delivery_id is not None and delivery_id in store.seen_delivery_ids
    if delivery_id:
        store.seen_delivery_ids.add(delivery_id)

    store.events.append(
        {
            "event": event_type,
            "delivery_id": delivery_id,
            "received_at": store.now(),
            "duplicate": duplicate,
            "payload": payload,
        }
    )
    logger.info("received event=%s delivery=%s duplicate=%s", event_type, delivery_id, duplicate)
    return {"received": True, "event": event_type, "duplicate": duplicate}


@app.post("/webhooks/flaky")
async def flaky(request: Request) -> dict:
    """A receiver that fails its first two attempts of each delivery."""
    delivery_id = request.headers.get("X-Webhook-Delivery", "anonymous")
    store.flaky_counts[delivery_id] = store.flaky_counts.get(delivery_id, 0) + 1
    attempt = store.flaky_counts[delivery_id]
    if attempt < 3:
        raise HTTPException(status_code=500, detail=f"boom (attempt {attempt})")
    return {"received": True, "after_attempts": attempt}


@app.post("/webhooks/dead")
async def dead() -> dict:
    """A receiver that never succeeds — deliveries here exhaust their retries."""
    raise HTTPException(status_code=500, detail="permanently down")


@app.get("/events")
async def list_events() -> list:
    return store.events


# ---------------------------------------------------------------- provider


@app.post("/subscriptions", status_code=201)
async def subscribe(req: SubscribeRequest) -> dict:
    sub_id = uuid.uuid4().hex[:8]
    store.subscriptions[sub_id] = req.url
    logger.info("subscribed %s -> %s", sub_id, req.url)
    return {"id": sub_id, "url": req.url}


@app.get("/subscriptions")
async def list_subscriptions() -> list:
    return [{"id": k, "url": v} for k, v in store.subscriptions.items()]


@app.delete("/subscriptions/{sub_id}", status_code=204)
async def unsubscribe(sub_id: str) -> None:
    if sub_id not in store.subscriptions:
        raise HTTPException(status_code=404, detail="No such subscription")
    del store.subscriptions[sub_id]


@app.post("/emit")
async def emit(req: EmitRequest) -> dict:
    """Fire an event at all subscribers.

    Real providers enqueue and return instantly; here we await the deliveries
    so you can see the whole result in one response (and tests stay simple).
    """
    event = {
        "id": "evt_" + uuid.uuid4().hex[:12],
        "type": req.type,
        "created_at": store.now(),
        "data": req.data,
    }
    results = await fan_out(event)
    return {
        "event": event,
        "subscribers": len(results),
        "deliveries": [
            {"url": r["url"], "status": r["status"], "attempts": len(r["attempts"])}
            for r in results
        ],
    }


@app.get("/deliveries")
async def list_deliveries() -> list:
    return store.deliveries


# ---------------------------------------------------------------- dashboard

STATIC_DIR = Path(__file__).parent / "static"


@app.post("/lab/{scenario}")
async def learning_lab(scenario: Literal["valid", "tampered", "duplicate"]) -> dict:
    delivery_id = uuid.uuid4().hex
    signed_body = json.dumps({"type": "lesson.ping", "data": {"amount": 10}}, separators=(",", ":"))
    sent_body = signed_body.replace('10', '99') if scenario == "tampered" else signed_body
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": "lesson.ping",
        "X-Webhook-Delivery": delivery_id,
        "X-Hub-Signature-256": sign(get_settings().webhook_secret, signed_body.encode()),
    }
    responses = []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://lab") as client:
        for _ in range(2 if scenario == "duplicate" else 1):
            response = await client.post("/webhooks/receive", content=sent_body.encode(), headers=headers)
            responses.append({"status": response.status_code, "body": response.json()})
    return {
        "scenario": scenario,
        "delivery_id": delivery_id,
        "signed_body": signed_body,
        "sent_body": sent_body,
        "responses": responses,
    }


@app.get("/state")
async def state() -> dict:
    """Everything the dashboard renders, in one JSON blob."""
    settings = get_settings()
    return {
        "subscriptions": [{"id": k, "url": v} for k, v in store.subscriptions.items()],
        "deliveries": store.deliveries,
        "events": store.events,
        "config": {
            "max_attempts": settings.max_attempts,
            "retry_delay_seconds": settings.retry_delay_seconds,
        },
    }


@app.get("/")
async def dashboard() -> FileResponse:
    """The interactive lifecycle dashboard — see docs/dashboard.md."""
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
