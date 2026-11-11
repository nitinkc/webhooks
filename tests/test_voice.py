from tests.conftest import twilio_post

CALL_PARAMS = {
    "CallSid": "CA" + "c" * 32,
    "AccountSid": "AC" + "0" * 32,
    "From": "+15551234567",
    "To": "+15555550100",
    "CallStatus": "ringing",
}


def test_inbound_call_returns_gather(client):
    resp = twilio_post(client, "/webhooks/voice/inbound", CALL_PARAMS)
    assert resp.status_code == 200
    assert "<Gather" in resp.text
    assert "<Say>" in resp.text
    assert 'action="/webhooks/voice/menu"' in resp.text


def test_menu_digit_1_confirms(client):
    resp = twilio_post(client, "/webhooks/voice/menu", {**CALL_PARAMS, "Digits": "1"})
    assert "confirmed" in resp.text
    assert "<Hangup" in resp.text


def test_menu_invalid_digit(client):
    resp = twilio_post(client, "/webhooks/voice/menu", {**CALL_PARAMS, "Digits": "9"})
    assert "not a valid option" in resp.text


def test_voice_requires_signature(client):
    resp = client.post("http://localhost:8000/webhooks/voice/inbound", data=CALL_PARAMS)
    assert resp.status_code == 403
