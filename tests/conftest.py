import json
import os
import uuid

# Deterministic test settings — env vars are set before app config is read.
os.environ["WEBHOOK_SECRET"] = "test-secret"
os.environ["MAX_ATTEMPTS"] = "3"
os.environ["RETRY_DELAY_SECONDS"] = "0.01"

import httpx
import pytest
from fastapi.testclient import TestClient

from app import dispatcher, store
from app.main import app
from app.security import sign

SECRET = "test-secret"
TESTSERVER = "http://testserver"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_store():
    store.events.clear()
    store.seen_delivery_ids.clear()
    store.subscriptions.clear()
    store.deliveries.clear()
    store.flaky_counts.clear()


@pytest.fixture
def asgi_transport(monkeypatch):
    """Make the dispatcher deliver in-process: 'http://testserver' URLs hit this app."""
    monkeypatch.setattr(
        dispatcher,
        "CLIENT_FACTORY",
        lambda: httpx.AsyncClient(transport=httpx.ASGITransport(app=app), timeout=5),
    )


def signed_post(
    client: TestClient,
    path: str,
    payload: dict,
    secret: str = SECRET,
    event: str = "test.event",
    delivery: str | None = None,
    signature: str | None = None,
):
    """POST like a provider would: JSON body + signature headers."""
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": event,
        "X-Webhook-Delivery": delivery or uuid.uuid4().hex,
        "X-Webhook-Attempt": "1",
        "X-Hub-Signature-256": signature if signature is not None else sign(secret, body),
    }
    return client.post(path, content=body, headers=headers)
