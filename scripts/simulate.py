#!/usr/bin/env python3
"""Replay real-shaped, cryptographically signed Twilio webhooks locally.

Twilio never has to know you exist: this script posts the same form-encoded
payloads Twilio would send, signed with the same HMAC-SHA1 algorithm, so the
server's X-Twilio-Signature validation runs for real.

Run from the repo root while the server is up:

    uv run python scripts/simulate.py --scenario all
    uv run python scripts/simulate.py --scenario sms-inbound --body CONFIRM
    uv run python scripts/simulate.py --scenario sms-status --status failed
"""

import argparse
import base64
import hashlib
import hmac
import sys
import uuid
from pathlib import Path

import httpx

# Make `app` importable when running as `python scripts/simulate.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402

PATIENT = "+15551234567"


def fake_sid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex.upper()


def compute_signature(url: str, params: dict, auth_token: str) -> str:
    """The exact algorithm Twilio's RequestValidator verifies:
    HMAC-SHA1(auth_token, url + concat(key + value for sorted keys)), base64."""
    payload = url + "".join(key + params[key] for key in sorted(params))
    digest = hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def post(client: httpx.Client, base_url: str, path: str, params: dict, token: str) -> httpx.Response:
    url = base_url.rstrip("/") + path
    signature = compute_signature(url, params, token)
    print(f"\n>>> POST {path}")
    for key in sorted(params):
        print(f"      {key}={params[key]}")
    resp = client.post(
        url,
        data=params,  # form-encoded, exactly like Twilio
        headers={"X-Twilio-Signature": signature},
    )
    print(f"<<< {resp.status_code}")
    if resp.text:
        print(resp.text)
    return resp


def sms_inbound(client, base, token, from_number, body):
    post(client, base, "/webhooks/sms/inbound", {
        "MessageSid": fake_sid("SM"),
        "AccountSid": "AC" + "0" * 32,
        "From": from_number,
        "To": get_settings().twilio_phone_number,
        "Body": body,
        "NumMedia": "0",
    }, token)


def sms_status(client, base, token, status):
    post(client, base, "/webhooks/sms/status", {
        "MessageSid": fake_sid("SM"),
        "AccountSid": "AC" + "0" * 32,
        "MessageStatus": status,
        "To": PATIENT,
        "From": get_settings().twilio_phone_number,
        "ErrorCode": "30007" if status in ("failed", "undelivered") else "",
    }, token)


def voice_call(client, base, token):
    post(client, base, "/webhooks/voice/inbound", {
        "CallSid": fake_sid("CA"),
        "AccountSid": "AC" + "0" * 32,
        "From": PATIENT,
        "To": get_settings().twilio_phone_number,
        "CallStatus": "ringing",
    }, token)


def voice_menu(client, base, token, digits):
    post(client, base, "/webhooks/voice/menu", {
        "CallSid": fake_sid("CA"),
        "AccountSid": "AC" + "0" * 32,
        "From": PATIENT,
        "To": get_settings().twilio_phone_number,
        "Digits": digits,
    }, token)


def run_all(client, base, token):
    print("\n=== 1. Patient replies CONFIRM to a reminder ===")
    sms_inbound(client, base, token, PATIENT, "CONFIRM")
    print("\n=== 2. Twilio reports the reminder was delivered ===")
    sms_status(client, base, token, "delivered")
    print("\n=== 3. Patient calls the number ===")
    voice_call(client, base, token)
    print("\n=== 4. Patient presses 1 in the menu ===")
    voice_menu(client, base, token, "1")


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=settings.app_base_url, help="server base URL")
    parser.add_argument("--auth-token", default=settings.twilio_auth_token, help="token used to sign requests")
    parser.add_argument("--from", dest="from_number", default=PATIENT, help="patient phone number")
    parser.add_argument("--body", default="CONFIRM", help="SMS body for sms-inbound")
    parser.add_argument("--status", default="delivered", help="MessageStatus for sms-status")
    parser.add_argument("--digits", default="1", help="DTMF digits for voice-menu")
    parser.add_argument(
        "--scenario",
        required=True,
        choices=["sms-inbound", "sms-status", "voice-call", "voice-menu", "all"],
    )
    args = parser.parse_args()

    with httpx.Client(timeout=10) as client:
        match args.scenario:
            case "sms-inbound":
                sms_inbound(client, args.url, args.auth_token, args.from_number, args.body)
            case "sms-status":
                sms_status(client, args.url, args.auth_token, args.status)
            case "voice-call":
                voice_call(client, args.url, args.auth_token)
            case "voice-menu":
                voice_menu(client, args.url, args.auth_token, args.digits)
            case "all":
                run_all(client, args.url, args.auth_token)


if __name__ == "__main__":
    main()
