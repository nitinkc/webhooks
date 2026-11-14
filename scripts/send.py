#!/usr/bin/env python3
"""Pretend to be an external webhook provider: POST one signed event to a URL.

While the server is running (uv run uvicorn app.main:app --reload):

    uv run python scripts/send.py --event order.created --data '{"order_id": 42}'
    uv run python scripts/send.py --url https://webhook.site/<your-id>
    uv run python scripts/send.py --bad-secret   # watch the 401
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.security import sign  # noqa: E402


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--url", default="http://localhost:8000/webhooks/receive",
        help="where to deliver the event",
    )
    parser.add_argument("--event", default="demo.ping", help="event type")
    parser.add_argument("--data", default="{}", help="JSON payload, e.g. '{\"order_id\": 42}'")
    parser.add_argument(
        "--secret", default=settings.webhook_secret,
        help="signing secret (default: WEBHOOK_SECRET from .env)",
    )
    parser.add_argument(
        "--bad-secret", action="store_true",
        help="sign with a wrong secret — the receiver should return 401",
    )
    args = parser.parse_args()

    event = {
        "id": "evt_" + uuid.uuid4().hex[:12],
        "type": args.event,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data": json.loads(args.data),
    }
    body = json.dumps(event, separators=(",", ":")).encode()
    secret = "forged-secret" if args.bad_secret else args.secret
    delivery_id = uuid.uuid4().hex
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-ID": event["id"],
        "X-Webhook-Event": event["type"],
        "X-Webhook-Delivery": delivery_id,
        "X-Webhook-Attempt": "1",
        "X-Hub-Signature-256": sign(secret, body),
    }

    print(f">>> POST {args.url}")
    print(f"    X-Webhook-Event:      {event['type']}")
    print(f"    X-Webhook-Delivery:   {delivery_id}")
    print(f"    X-Hub-Signature-256:  {headers['X-Hub-Signature-256'][:24]}...")
    print(f"    body: {body.decode()}")

    resp = httpx.post(args.url, content=body, headers=headers, timeout=10)
    print(f"<<< {resp.status_code} {resp.text}")


if __name__ == "__main__":
    main()
