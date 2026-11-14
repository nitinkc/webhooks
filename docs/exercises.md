# Exercises

Hands-on tasks, roughly in order of difficulty. Each one maps to a real
concept from these docs.

## Browser learning path

Start the app with `uv run uvicorn app.main:app --reload` and open
<http://localhost:8000>. Predict the outcome before each action:

1. **Send a valid webhook**: expect `200` and a new received event.
2. **Send a tampered webhook**: expect `401` and no new received event.
   Expand the experiment inspector: which exact bytes changed?
3. **Replay a delivery**: expect two `200`s sharing one delivery ID, with
   `duplicate: true` in the second response. Why acknowledge a duplicate?
4. Add **healthy**, **flaky**, and **dead** subscribers; emit one event.
   Expect separate delivery IDs but the same event ID. With default settings,
   healthy takes one attempt, flaky takes three, dead exhausts four.
5. Expand a delivery and inspect the raw body and signature header.
   Why would pretty-printing the JSON before verification be incorrect?

The lab calls the real receiver in-process; retries use actual HTTP callbacks.
Only healthy/lab requests appear in Received events; flaky/dead simulate status
codes only. State resets on server restart. See [The dashboard](dashboard.md)
for the UI/API mapping, then try the command-line and coding exercises below.

## 1. Forge and get rejected

```bash
uv run python scripts/send.py --bad-secret
```

**Question:** the receiver returns `401`, not `400`. Why is that the right
status code? What would `403` imply instead?

## 2. Watch retries happen

```bash
uv run uvicorn app.main:app --reload     # terminal 1
uv run python scripts/demo.py            # terminal 2
```

In the output, `/webhooks/flaky` shows `[500, 500, 200]` and `/webhooks/dead`
shows `[500, 500, 500, 500]`. Open `GET /deliveries` and check the `attempts`
array — the same `X-Webhook-Delivery` ID, rising `X-Webhook-Attempt`
numbers, growing gaps (0.5s → 1s → 2s).

**Question:** why does the retry of a delivery reuse the delivery ID, and
what does the receiver do with that?

## 3. Inspect a delivery from the outside

Create a free URL at [webhook.site](https://webhook.site), then:

```bash
curl -X POST localhost:8000/subscriptions \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://webhook.site/<your-id>"}'
uv run python scripts/demo.py
```

Compare what webhook.site shows (headers, raw body) with what the local
receiver recorded in `GET /events`.

## 4. Add replay protection (Stripe-style)

Modify `dispatcher.py` to add an `X-Webhook-Timestamp` header and sign
`timestamp.body` instead of just `body`. Modify the receiver to reject
timestamps older than 5 minutes — *before* checking dedup.

**Concepts:** why does signing the timestamp prevent an attacker from
stripping it? What breaks if subscriber and provider clocks drift?

## 5. Write a receiver in another language

The signature scheme is ~5 lines of stdlib HMAC anywhere — that's the point
of the standard. Write a receiver in Java (Spring Boot, Javalin, or the
JDK's built-in `HttpServer`), Node (`express`/`crypto`), or Go:

```text
1. read raw body bytes
2. expected = "sha256=" + hex(HMAC_SHA256(secret, body))
3. constant-time compare with X-Hub-Signature-256
4. 200 on match, 401 otherwise
```

Then point `send.py` at it: `uv run python scripts/send.py --url http://localhost:<port>/...`.

**Bonus:** run it on a second machine or VM and subscribe *its* LAN/public
URL to the local provider — now the two sides really are separate servers.

## 6. Go live with GitHub

Follow [Exposing your server](exposing.md) to receive a genuine signed
`push` event. Then find GitHub's "Recent Deliveries" tab and compare its
view of the delivery with your `/deliveries` log — same concept, provider
and subscriber side.

## 7. Compare with the other transports

Run the sibling playgrounds — `../websockets-101` and `../grpc-101` — and
emit the same `order.created` event in each. Now kill each server
mid-delivery.

**Question:** which subscribers notice, and how? What machinery does each
mechanism need to tolerate the other side being down?
