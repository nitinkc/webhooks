from tests.conftest import twilio_post

SMS_PARAMS = {
    "MessageSid": "SM" + "a" * 32,
    "AccountSid": "AC" + "0" * 32,
    "From": "+15551234567",
    "To": "+15555550100",
    "NumMedia": "0",
}


def inbound(client, body: str):
    return twilio_post(client, "/webhooks/sms/inbound", {**SMS_PARAMS, "Body": body})


def test_inbound_sms_returns_twiml(client):
    resp = inbound(client, "hello")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    assert "<Response>" in resp.text and "<Message>" in resp.text


def test_confirm_keyword(client):
    resp = inbound(client, "CONFIRM")
    assert "Confirmed" in resp.text


def test_keywords_are_case_insensitive(client):
    assert "Confirmed" in inbound(client, "  confirm  ").text


def test_stop_keyword(client):
    assert "unsubscribed" in inbound(client, "STOP").text


def test_unknown_text_gets_help_menu(client):
    resp = inbound(client, "asdkjh")
    assert "Patient Companion" in resp.text


def test_status_callback_returns_204(client):
    resp = twilio_post(client, "/webhooks/sms/status", {
        "MessageSid": "SM" + "b" * 32,
        "MessageStatus": "delivered",
        "To": "+15551234567",
        "From": "+15555550100",
    })
    assert resp.status_code == 204


def test_missing_signature_rejected(client):
    resp = client.post("http://localhost:8000/webhooks/sms/inbound", data={**SMS_PARAMS, "Body": "CONFIRM"})
    assert resp.status_code == 403


def test_bad_signature_rejected(client):
    resp = twilio_post(
        client, "/webhooks/sms/inbound", {**SMS_PARAMS, "Body": "CONFIRM"}, signature="forged"
    )
    assert resp.status_code == 403


def test_tampered_body_rejected(client):
    # Sign a payload with one body, then send a different one.
    from tests.conftest import sign
    params = {**SMS_PARAMS, "Body": "CONFIRM"}
    sig = sign("http://localhost:8000/webhooks/sms/inbound", params)
    params["Body"] = "STOP"
    resp = twilio_post(client, "/webhooks/sms/inbound", params, signature=sig)
    assert resp.status_code == 403
