# The dashboard

Open <http://localhost:8000> while the server is running. The dashboard is a
live view of the **entire webhook lifecycle** — one app playing both roles,
so you can watch a delivery travel from "something happened" to "event
received" in real time. It polls `GET /state` every 1.5 seconds; everything
it does can also be done by hand through the API (`/docs`).

```text
Provider (this app) ──signed HTTP POST──► Subscriber (this app)
   /emit, dispatcher.py   X-Hub-Signature-256   /webhooks/receive
```

## Start here: predict, run, inspect

Start with the three experiment cards. No subscriptions or terminal commands
are needed after starting the server.

| Experiment | Predict | Observe | Learn |
| --- | --- | --- | --- |
| Send a valid webhook | Will a matching signature pass? | `200`, one new received event | HMAC authenticates the exact body bytes |
| Send a tampered webhook | Can a changed amount pass? | `401`, no received event | Changing `10` to `99` after signing invalidates the signature |
| Replay a delivery | Will the second request be rejected? | Two `200`s, then `duplicate: true` | Acknowledge retries while preventing repeated business work |

Open **Inspect experiment bodies and responses** to compare `signed_body`,
`sent_body`, the delivery ID, and HTTP responses. These buttons call
`POST /lab/valid`, `/lab/tampered`, and `/lab/duplicate`. The lab invokes the
real `/webhooks/receive` handler in-process, never an arbitrary target, and
never returns the configured signing secret. It does not create provider
`/deliveries` entries; inspect **Received events** instead.

The app logs both duplicate receipts and flags the second. It does not implement
a database-backed business-processing queue. Deduplication is in memory and
resets on restart; real systems need persistent idempotency records. The UI
shows connection errors and reports invalid event JSON without sending it.

## ① Subscribers — who's listening

This is the **subscription step**: the moment you paste a URL into GitHub's
*Settings → Webhooks*. A subscriber is just a URL the provider will POST to.

- **+ healthy receiver** — subscribes `/webhooks/receive`. Verifies the
  signature, dedupes, records the event.
- **+ flaky receiver** — subscribes `/webhooks/flaky`. Returns `500` for the
  first two attempts of every delivery, then succeeds — this is how you
  *see* retries happen.
- **+ dead receiver** — subscribes `/webhooks/dead`. Always fails, so you
  can watch a delivery exhaust its retries and die.
- Paste any public URL (e.g. a `webhook.site` URL) to see what a delivery
  looks like from the outside.

See [The players](concepts/roles.md) for why the *URL owner* is the
subscriber, and [Exposing your server](exposing.md) to give localhost a
public URL.

## ② Emit — "something happened"

`POST /emit` plays the role of *the event itself* — a `push` on GitHub, an
`invoice.paid` on Stripe. The provider serializes the event, signs it, and
fans out to every subscriber in parallel. The packet animation on the wire
marks this moment.

## ③ Deliveries — provider side

One card per delivery: event type, target URL, final status, and an
**attempt timeline** — each attempt's HTTP status with the backoff delay
between them (`0.5s → 1s → 2s`, configurable via `RETRY_DELAY_SECONDS` and
`MAX_ATTEMPTS`).

Click a card to inspect the **exact request that was sent**:

- the headers — `X-Webhook-Event`, `X-Webhook-ID`, `X-Webhook-Delivery`,
  `X-Webhook-Attempt`, and `X-Hub-Signature-256` (highlighted). These mirror
  GitHub's `X-GitHub-*` headers — see
  [Anatomy of a delivery](concepts/anatomy.md).
- the raw body — the signature covers **these bytes**, which is why
  receivers must verify the raw body, not re-serialized JSON
  ([Security](security.md)).
- the delivery ID — the idempotency key a receiver dedupes on
  ([Receiving](receiving.md)).

## ④ Received events — subscriber side

What `/webhooks/receive` accepted. Each row shows the three things a correct
receiver does:

1. **✓ signature verified** — anything failing this got a `401` and never
   appears here. (Forge one with `scripts/send.py --bad-secret`.)
2. **✓ new delivery id / ⚠ duplicate** — retries mean the same delivery can
   arrive twice; receivers dedupe on the delivery ID.
3. **✓ 200 OK returned** — respond fast; a slow receiver just triggers
   retries. Click a row to see the payload it recorded.

## Try this sequence

1. Subscribe the **healthy** receiver → emit → one attempt, `200`.
2. Subscribe **flaky** → emit → attempts `500, 500, 200` with waits between.
3. Subscribe **dead** → emit → `MAX_ATTEMPTS` failures (four by default), status `failed`.
   Flaky/dead are status simulators: neither verifies signatures nor adds to Received events.
   Flaky succeeds on attempt three only when `MAX_ATTEMPTS` is at least three.
4. Subscribe a `webhook.site` URL → emit → compare what it saw with ④.
5. `uv run python scripts/send.py --bad-secret` → the event never reaches ④.

Then work through the [exercises](exercises.md).
