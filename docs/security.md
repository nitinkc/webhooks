# Security: how a receiver knows a request is genuine

Your webhook URL is public — anyone who finds it can `POST` fake
`"payment.succeeded"` events. Signatures fix that: the provider proves it
knows a secret only the two of you share.

## HMAC-SHA256, the universal scheme

This repo implements **GitHub's exact scheme** in `app/security.py`:

```python
def sign(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"

def verify(secret: str, body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    return hmac.compare_digest(sign(secret, body), signature)
```

```http
X-Hub-Signature-256: sha256=<hex of HMAC-SHA256(secret, raw body)>
```

HMAC needs no special crypto library — it's two nested hashes of
`secret ⊕ pad ∥ message`. Same mechanism in Shopify (`X-Shopify-Hmac-Sha256`,
base64 instead of hex), Slack (`X-Slack-Signature`), and the
[Standard Webhooks](https://www.standardwebhooks.com) spec.

## Three subtleties that bite people

### 1. Sign the raw bytes, not the parsed JSON

`{"a":1}` and `{ "a" : 1 }` parse to the same object but are different
bytes — different signatures. Verifying a re-serialized body fails
intermittently depending on your JSON encoder's key order and whitespace.
That's why `main.py` calls `await request.body()` *before* `json.loads`.

### 2. Constant-time comparison

`==` returns at the first differing byte. An attacker measuring response
times can forge a valid signature one byte at a time (~256 guesses per byte
instead of 2^256). `hmac.compare_digest` takes the same time regardless of
where strings differ. Never use `==` on signatures, tokens, or secrets.

### 3. Replay attacks — the missing piece here

A signature proves the sender knew the secret *at some point* — but nothing
stops an attacker from **re-sending a captured valid request** an hour later.
Mitigations:

- **Delivery ID dedup** (this repo): replaying the same delivery is flagged
  as a duplicate. Effective when the delivery ID is unique per send.
- **Timestamped signatures** (Stripe-style): the header carries
  `t=<unix>,v1=<sig>` and the signed string is `t.body`. Reject requests
  older than ~5 minutes — a replayed signature is both tamper-evident and
  expired.
- **HTTPS everywhere**: a signature can't be *read* off the wire and reused
  if it expires, but TLS is still mandatory in production so the payload
  itself isn't intercepted in the first place.

Adding a timestamp check is [exercise 4](exercises.md).

## The secret

`WEBHOOK_SECRET` in `.env` — the shared key both sides sign with. In this
repo, provider and receiver are the same process so one secret signs and
verifies. In the wild:

- The subscriber picks (or is given) the secret at subscription time —
  GitHub's "Secret" field, Stripe's "signing secret" per endpoint.
- Per-endpoint secrets, not per-account: compromising one subscriber's
  secret shouldn't let you forge events to others.
- Rotate it: providers typically let you roll secrets without downtime.

## What signatures don't do

| They do | They don't |
|---|---|
| Prove the sender knows the secret | Encrypt anything — the body is plaintext over TLS |
| Prove the body wasn't modified | Stop replays (without a timestamp/dedup) |
| Let you trust the payload | Identify *which* sender, if many share the secret |

Also note: this scheme does **not** sign the URL, so it survives tunnels
and proxies that rewrite hosts — unlike Twilio's scheme which signs the
full request URL (the #1 source of Twilio webhook bugs behind proxies).
