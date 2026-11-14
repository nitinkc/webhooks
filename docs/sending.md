# Sending webhooks — being the notification server

The provider side: when something happens in *your* system, deliver a signed
event to everyone who subscribed. In this repo that's `POST /subscriptions`,
`POST /emit`, and `app/dispatcher.py`.

## The four moving parts

### 1. A subscription registry

Subscribers tell you where to send events:

```bash
curl -X POST localhost:8000/subscriptions \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://me.example/webhooks/receive"}'
```

Real providers let subscribers also pick *which event types* they want
(GitHub's per-event checkboxes) and set their own secret.

### 2. An event → delivery fan-out

When an event happens, it becomes one delivery *per subscriber*:

```python
# POST /emit
event = {"id": "evt_…", "type": req.type, "created_at": now(), "data": req.data}
await asyncio.gather(*(deliver(event, url) for url in subscribers))
```

!!! note "This repo awaits deliveries inline for transparency"
    A production provider never does this — events go into a **queue**
    (SQS, Kafka, a DB-backed job table) and workers deliver them
    asynchronously. We await so you can see the whole result in one
    response and tests stay deterministic. If you build this for real,
    [Svix](tools.md) is the open-source project that already solved it.

### 3. Signed POST with delivery headers

Each delivery gets a **fresh delivery ID** (shared across its retries) and
carries the event, signed with the shared secret:

```python
body = json.dumps(event).encode()
headers = {
    "X-Webhook-ID": event["id"],         # the event
    "X-Webhook-Event": event["type"],    # what happened
    "X-Webhook-Delivery": delivery_id,   # this delivery (dedupe key)
    "X-Webhook-Attempt": str(attempt),   # retry counter
    "X-Hub-Signature-256": sign(secret, body),
}
```

### 4. Retries with exponential backoff

Subscribers go down — deploys, crashes, network blips. A delivery engine
that gives up on the first `500` loses events, so we retry:

```python
for attempt in range(1, max_attempts + 1):
    status = await client.post(url, ...)
    if 200 <= status < 300:
        return "success"
    await asyncio.sleep(retry_delay * 2 ** (attempt - 1))   # 0.5s, 1s, 2s…
return "failed"
```

| This repo (demo) | Production-grade (GitHub/Stripe/Svix) |
|---|---|
| 4 attempts over ~4 seconds | Hours to days of retries |
| Fixed in-process `asyncio.sleep` | Durable queue with scheduled retries |
| In-memory delivery log | Per-endpoint disable after N failures |
| Single shared secret | Per-endpoint signing secrets |

Watch it live: subscribe `/webhooks/flaky`, emit an event, and the delivery
log shows `[500, 500, 200]` — succeeded on attempt 3.

## Send a webhook by hand

`scripts/send.py` acts as an external provider: it creates one event, signs its
raw JSON bytes, and POSTs directly to a receiver. Unlike `/emit`, it does not
use the subscription registry or create entries in the provider delivery log.
Accepted local requests still appear in `/events` and the dashboard.

With the local server running, use another terminal in the repository root:

```bash
uv run python scripts/send.py --event order.created --data '{"order_id": 42}'
uv run python scripts/send.py --bad-secret
```

Expect `200` for the signed request and `401` for the forged signature. The
script reads `WEBHOOK_SECRET` from `.env`, just like the server. To use another
local port, pass the full receiver URL:

```bash
uv run python scripts/send.py --url http://localhost:8002/webhooks/receive
```

To inspect the request externally, create your own URL at
[webhook.site](https://webhook.site) and replace the placeholder below. Send
only synthetic data to third-party services:

```bash
uv run python scripts/send.py --url 'https://webhook.site/<your-id>'
```

For the full fan-out and retry demo, run `uv run python scripts/demo.py`. It
registers healthy, flaky, and dead receivers and emits two events. With default
settings, healthy succeeds once, flaky succeeds on attempt three, and dead
exhausts four attempts. On another port, set `WEBHOOKS_BASE_URL`:

```bash
WEBHOOKS_BASE_URL=http://localhost:8002 uv run python scripts/demo.py
```

The scripts need a running server; browser-only experiments and their expected
results are covered in [The dashboard](dashboard.md) and [Exercises](exercises.md).

## "How do I expose myself as a webhook notification server?"

Two different questions hide in that phrase — this repo answers both:

**You want to *receive* notifications (be the subscriber):**
your endpoint must be publicly reachable over HTTPS. Locally that's a
tunnel — see [Exposing your server](exposing.md).

**You want to *send* notifications (be the provider):**

1. Your service must already be publicly reachable (subscribers need to call
   your subscribe API — tunnels work here too).
2. Expose a subscription API (`POST /subscriptions` here).
3. When events happen in your domain, fan out to subscribers as above.
4. Sign every delivery with a secret the subscriber knows.
5. Retry, log deliveries, and give subscribers a way to see failures —
   `GET /deliveries` here is a toy version of GitHub's "Recent Deliveries"
   tab or Stripe's event resend UI.

The minimal viable contract: *given a URL and a secret, POST signed JSON to
it when X happens, retrying on failure.* Everything else — event filters,
delivery logs, endpoint health scoring — is polish on top.
