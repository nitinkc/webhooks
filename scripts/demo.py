#!/usr/bin/env python3
"""The whole webhook lifecycle in one command.

Prerequisite — the server must be running:

    uv run uvicorn app.main:app --reload

This script then:
  1. subscribes three of the app's own endpoints (receive, flaky, dead)
  2. emits two events through the provider side
  3. prints the delivery log — watch flaky retry and dead exhaust retries

Then open http://localhost:8000 to see the live dashboard.
"""

import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = os.environ.get("WEBHOOKS_BASE_URL", "http://localhost:8000")


def ensure_subscription(client: httpx.Client, path: str) -> None:
    url = BASE + path
    if any(s["url"] == url for s in client.get(f"{BASE}/subscriptions").json()):
        return
    client.post(f"{BASE}/subscriptions", json={"url": url})


def emit(client: httpx.Client, event_type: str, data: dict) -> None:
    resp = client.post(f"{BASE}/emit", json={"type": event_type, "data": data})
    resp.raise_for_status()
    for d in resp.json()["deliveries"]:
        print(f"  {d['status']:>8}  {d['attempts']} attempt(s)  -> {d['url']}")


def main() -> None:
    with httpx.Client(timeout=30) as client:
        try:
            client.get(f"{BASE}/health").raise_for_status()
        except httpx.HTTPError:
            sys.exit(f"Server not reachable at {BASE} — start it with: uv run uvicorn app.main:app --reload")

        print("1. Subscribing the app's own endpoints...")
        for path in ("/webhooks/receive", "/webhooks/flaky", "/webhooks/dead"):
            ensure_subscription(client, path)

        print("\n2. Emitting events to all subscribers...")
        print(" demo.ping:")
        emit(client, "demo.ping", {"hello": "world"})
        print(" order.created:")
        emit(client, "order.created", {"order_id": 42, "total": "9.99"})

        print("\n3. Delivery log:")
        for d in client.get(f"{BASE}/deliveries").json():
            attempts = ", ".join(str(a["status"] or a["error"]) for a in d["attempts"])
            print(f"  {d['event']:<15} {d['status']:>8}  [{attempts}]  {d['url']}")

        print(f"\nDone — open {BASE} for the dashboard, {BASE}/docs for the API.")


if __name__ == "__main__":
    main()
