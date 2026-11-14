import json

from app import store
from app.security import sign, verify
from tests.conftest import SECRET, TESTSERVER, signed_post


# ------------------------------------------------------------- signatures


def test_sign_verify_roundtrip():
    sig = sign(SECRET, b'{"a":1}')
    assert sig.startswith("sha256=")
    assert verify(SECRET, b'{"a":1}', sig)


def test_verify_rejects_wrong_secret():
    assert not verify("other-secret", b'{"a":1}', sign(SECRET, b'{"a":1}'))


def test_verify_rejects_tampered_body():
    assert not verify(SECRET, b'{"a":2}', sign(SECRET, b'{"a":1}'))


def test_verify_rejects_missing_signature():
    assert not verify(SECRET, b'{"a":1}', None)


# ------------------------------------------------------------- receiver


def test_receive_accepts_valid_signature(client):
    resp = signed_post(client, "/webhooks/receive", {"type": "test.event", "data": {"x": 1}})
    assert resp.status_code == 200
    assert resp.json()["event"] == "test.event"
    assert store.events[-1]["payload"]["data"] == {"x": 1}


def test_receive_rejects_bad_signature(client):
    resp = signed_post(client, "/webhooks/receive", {"a": 1}, signature="sha256=forged")
    assert resp.status_code == 401


def test_receive_rejects_missing_signature(client):
    resp = client.post("/webhooks/receive", content=b'{"a":1}')
    assert resp.status_code == 401


def test_receive_rejects_tampered_body(client):
    # Sign one payload, send a different one.
    sig = sign(SECRET, b'{"data":"original"}')
    resp = client.post(
        "/webhooks/receive",
        content=b'{"data":"tampered"}',
        headers={"X-Hub-Signature-256": sig},
    )
    assert resp.status_code == 401


def test_receive_detects_duplicate_delivery(client):
    delivery = "deadbeef"
    first = signed_post(client, "/webhooks/receive", {"a": 1}, delivery=delivery)
    second = signed_post(client, "/webhooks/receive", {"a": 1}, delivery=delivery)
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True


# ------------------------------------------------------------- provider


def test_subscribe_list_unsubscribe(client):
    resp = client.post("/subscriptions", json={"url": TESTSERVER + "/webhooks/receive"})
    assert resp.status_code == 201
    sub_id = resp.json()["id"]
    assert client.get("/subscriptions").json() == [
        {"id": sub_id, "url": TESTSERVER + "/webhooks/receive"}
    ]
    assert client.delete(f"/subscriptions/{sub_id}").status_code == 204
    assert client.get("/subscriptions").json() == []


def test_emit_with_no_subscribers(client):
    resp = client.post("/emit", json={"type": "demo.ping", "data": {}})
    assert resp.status_code == 200
    assert resp.json()["subscribers"] == 0
    assert resp.json()["event"]["type"] == "demo.ping"


def test_emit_delivers_signed_event(client, asgi_transport):
    client.post("/subscriptions", json={"url": TESTSERVER + "/webhooks/receive"})
    resp = client.post("/emit", json={"type": "order.created", "data": {"order_id": 42}})
    delivery = resp.json()["deliveries"][0]
    assert delivery["status"] == "success"
    assert delivery["attempts"] == 1
    # The receiver side recorded it, and verified the signature itself.
    assert store.events[-1]["event"] == "order.created"


def test_retries_until_flaky_receiver_succeeds(client, asgi_transport):
    client.post("/subscriptions", json={"url": TESTSERVER + "/webhooks/flaky"})
    resp = client.post("/emit", json={"type": "demo.ping"})
    delivery = resp.json()["deliveries"][0]
    assert delivery["status"] == "success"
    assert delivery["attempts"] == 3  # 500, 500, 200
    assert [a["status"] for a in store.deliveries[-1]["attempts"]] == [500, 500, 200]


def test_dead_receiver_exhausts_retries(client, asgi_transport):
    client.post("/subscriptions", json={"url": TESTSERVER + "/webhooks/dead"})
    resp = client.post("/emit", json={"type": "demo.ping"})
    delivery = resp.json()["deliveries"][0]
    assert delivery["status"] == "failed"
    assert delivery["attempts"] == 3  # MAX_ATTEMPTS from conftest env


# ------------------------------------------------------------- misc


def test_learning_lab_valid_delivery(client):
    response = client.post('/lab/valid')
    assert response.status_code == 200
    assert response.json()['responses'][0]['status'] == 200
    assert len(store.events) == 1


def test_learning_lab_tampered_delivery(client):
    result = client.post('/lab/tampered').json()
    assert result['responses'][0]['status'] == 401
    assert result['signed_body'] != result['sent_body']
    assert store.events == []


def test_learning_lab_duplicate_delivery(client):
    result = client.post('/lab/duplicate').json()
    assert [r['body']['duplicate'] for r in result['responses']] == [False, True]
    assert len({e['delivery_id'] for e in store.events}) == 1


def test_learning_lab_rejects_unknown_scenario(client):
    assert client.post('/lab/unknown').status_code == 422


def test_dashboard_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "webhooks-101" in resp.text
