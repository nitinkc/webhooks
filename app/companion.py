"""Patient-companion reply logic — the "brain" behind the SMS webhook.

Deliberately framework-free and Twilio-free: it maps a patient's reply text
to an answer. Swap the canned strings for real patient lookup (by From
number), appointment systems, or a database without touching the routers.
"""

import logging

from app import twilio_client

logger = logging.getLogger(__name__)

HELP_REPLY = (
    "Patient Companion: reply CONFIRM to confirm your appointment, "
    "RESCHEDULE to pick a new time, TAKEN if you took your meds, "
    "or STOP to unsubscribe."
)

# In a real app these come from the patient's actual schedule.
APPOINTMENT = "Tue Nov 18 at 3:00 PM"


def reply_for(body: str, from_number: str) -> str:
    keyword = body.strip().upper()
    first_word = keyword.split(maxsplit=1)[0] if keyword else ""
    logger.info("inbound SMS from %s: %r -> keyword %r", from_number, body, first_word)

    match first_word:
        case "CONFIRM":
            # Exercises the outbound path too: a separate follow-up SMS sent
            # via the API (mock-logged locally) on top of the TwiML reply.
            twilio_client.send_sms(
                from_number, "Reminder: please arrive 15 minutes early and bring your ID."
            )
            return f"Confirmed! We'll see you {APPOINTMENT}."
        case "CANCEL":
            return f"Your appointment {APPOINTMENT} has been cancelled. Reply RESCHEDULE anytime."
        case "RESCHEDULE":
            return "No problem — reply with a day (e.g. THURSDAY) and we'll offer times."
        case "TAKEN":
            return "Dose logged. Great job staying on schedule!"
        case "SKIP":
            return "Logged as skipped. If this keeps happening, reply HELP to reach your care team."
        case "STOP":
            return "You are unsubscribed and will no longer receive messages. Reply START to rejoin."
        case "HELP" | "START":
            return HELP_REPLY
        case _:
            return HELP_REPLY
