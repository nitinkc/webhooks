"""SMS webhooks.

POST /webhooks/sms/inbound — Twilio calls this when a patient texts your number.
    You reply with TwiML (<Response><Message>...) which Twilio turns into an SMS.

POST /webhooks/sms/status — Twilio calls this as a sent message changes state
    (queued -> sent -> delivered, or failed/undelivered). Nothing to return;
    it's purely informational — the delivery-tracking half of reminders.
"""

import logging

from fastapi import APIRouter, Depends, Request, Response
from twilio.twiml.messaging_response import MessagingResponse

from app import companion
from app.security import verify_twilio_signature

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webhooks/sms",
    tags=["sms"],
    dependencies=[Depends(verify_twilio_signature)],
)


@router.post("/inbound")
async def inbound_sms(request: Request) -> Response:
    form = await request.form()
    reply_text = companion.reply_for(
        body=str(form.get("Body", "")),
        from_number=str(form.get("From", "")),
    )
    twiml = MessagingResponse()
    twiml.message(reply_text)
    return Response(str(twiml), media_type="application/xml")


@router.post("/status")
async def sms_status(request: Request) -> Response:
    form = await request.form()
    logger.info(
        "SMS status: sid=%s status=%s error=%s to=%s",
        form.get("MessageSid"),
        form.get("MessageStatus"),
        form.get("ErrorCode") or "-",
        form.get("To"),
    )
    # Twilio only needs a 2xx — the body is ignored.
    return Response(status_code=204)
