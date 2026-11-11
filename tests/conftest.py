import base64
import hashlib
import hmac
import os

# Deterministic test settings — real env vars beat .env in pydantic-settings.
os.environ["TWILIO_AUTH_TOKEN"] = "test-token"
os.environ["TWILIO_ACCOUNT_SID"] = ""
os.environ["APP_BASE_URL"] = "http://localhost:8000"
os.environ["MOCK_MODE"] = "true"

import pytest
from fastapi.testclient import TestClient

from app.main import app

BASE_URL = "http://localhost:8000"
AUTH_TOKEN = "test-token"


def sign(url: str, params: dict) -> str:
    payload = url + "".join(k + params[k] for k in sorted(params))
    digest = hmac.new(AUTH_TOKEN.encode(), payload.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def twilio_post(client: TestClient, path: str, params: dict, signature: str | None = None):
    """POST like Twilio would: form-encoded + X-Twilio-Signature header."""
    url = BASE_URL + path
    headers = {"X-Twilio-Signature": signature if signature is not None else sign(url, params)}
    return client.post(url, data=params, headers=headers)
