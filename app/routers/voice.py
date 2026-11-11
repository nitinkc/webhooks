"""Voice webhooks — a minimal IVR.

POST /webhooks/voice/inbound — Twilio calls this when someone phones your number.
    We answer with <Gather>: play a greeting, collect one digit, then POST the
    digit to /webhooks/voice/menu.

POST /webhooks/voice/menu — receives Digits and speaks the result.
    This request->TwiML->request loop is how every Twilio IVR works: each step
    is a fresh HTTP call, your server is the state machine.
"""

import logging

from fastapi import APIRouter, Depends, Request, Response
from twilio.twiml.voice_response import Gather, VoiceResponse

from app.security import verify_twilio_signature

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/webhooks/voice",
    tags=["voice"],
    dependencies=[Depends(verify_twilio_signature)],
)


@router.post("/inbound")
async def inbound_call(request: Request) -> Response:
    form = await request.form()
    logger.info("inbound call: sid=%s from=%s", form.get("CallSid"), form.get("From"))

    twiml = VoiceResponse()
    gather = Gather(num_digits=1, action="/webhooks/voice/menu", method="POST")
    gather.say(
        "Hello! Thanks for calling your patient companion. "
        "Press 1 to confirm your appointment. "
        "Press 2 to reschedule. "
        "Press 3 for the nurse line."
    )
    twiml.append(gather)
    twiml.say("We didn't receive any input. Goodbye.")  # Gather timed out
    return Response(str(twiml), media_type="application/xml")


@router.post("/menu")
async def voice_menu(request: Request) -> Response:
    form = await request.form()
    digits = str(form.get("Digits", ""))
    logger.info("menu selection: call=%s digits=%s", form.get("CallSid"), digits)

    twiml = VoiceResponse()
    match digits:
        case "1":
            twiml.say("Your appointment is confirmed. A text reminder is on its way.")
        case "2":
            twiml.say("We'll text you a link to pick a new time.")
        case "3":
            twiml.say("Connecting you to the nurse line now.")
        case _:
            twiml.say("Sorry, that's not a valid option.")
    twiml.hangup()
    return Response(str(twiml), media_type="application/xml")
