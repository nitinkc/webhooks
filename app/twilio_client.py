"""Outbound SMS via Twilio — real client when creds exist, mock otherwise.

This is the single seam between the app and the Twilio API: when you add
real credentials and set MOCK_MODE=false, only this file's behavior changes.
"""

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


def send_sms(to: str, body: str) -> str:
    """Send an SMS. Returns the message SID (or 'MOCK' in mock mode)."""
    settings = get_settings()

    if settings.mock_mode or not settings.has_real_credentials:
        logger.info("[MOCK] SMS -> %s: %s", to, body)
        return "MOCK"

    from twilio.rest import Client

    message = Client(settings.twilio_account_sid, settings.twilio_auth_token).messages.create(
        to=to,
        from_=settings.twilio_phone_number,
        body=body,
    )
    logger.info("sent SMS %s -> %s", message.sid, to)
    return message.sid
