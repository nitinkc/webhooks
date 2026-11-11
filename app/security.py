"""X-Twilio-Signature verification.

Twilio signs every webhook POST with your Auth Token. The signature is
HMAC-SHA1 over (url + sorted POST params), base64-encoded, sent in the
X-Twilio-Signature header. Verifying it proves the request really came
from Twilio and wasn't forged or tampered with — critical for anything
touching patient data.

The simulator (scripts/simulate.py) uses the same algorithm, so validation
runs for real locally — flip TWILIO_AUTH_TOKEN to a real token later and
nothing else changes.
"""

import logging

from fastapi import HTTPException, Request
from twilio.request_validator import RequestValidator

from app.config import get_settings

logger = logging.getLogger(__name__)


async def verify_twilio_signature(request: Request) -> None:
    settings = get_settings()
    if not settings.validate_signatures:
        logger.warning("TWILIO_AUTH_TOKEN not set — skipping signature validation")
        return

    signature = request.headers.get("X-Twilio-Signature", "")
    form = await request.form()  # cached; the route can call request.form() again

    # The validator checks the signature against the exact URL Twilio called.
    # Locally that's APP_BASE_URL + path; behind ngrok/a proxy it must be the
    # public URL (watch out for https->http scheme rewriting).
    url = settings.app_base_url.rstrip("/") + request.url.path

    if not RequestValidator(settings.twilio_auth_token).validate(url, dict(form), signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
