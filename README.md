# Patient Companion — Twilio Webhook Sandbox

A local sandbox for the webhook flows a patient companion app needs: **inbound
SMS replies**, **delivery status callbacks**, and a **voice IVR**. Runs
end-to-end with **zero Twilio credentials** — a simulator replays real-shaped,
cryptographically signed Twilio payloads against your local server.

## Quickstart

```bash
uv sync
cp .env.example .env

# terminal 1 — the server
uv run uvicorn app.main:app --reload

# terminal 2 — play Twilio
uv run python scripts/simulate.py --scenario all
```

Other scenarios:

```bash
uv run python scripts/simulate.py --scenario sms-inbound --body "TAKEN"
uv run python scripts/simulate.py --scenario sms-status --status failed
uv run python scripts/simulate.py --scenario voice-call
uv run python scripts/simulate.py --scenario voice-menu --digits 2
```

Try unsigned/forged requests — they get `403`. Tests: `uv run pytest`.
Interactive docs: http://localhost:8000/docs

## How it works — the tech

### What a webhook is (in this context)

You don't call Twilio for most of this — **Twilio calls you**. When a patient
texts your Twilio number, Twilio makes an HTTP `POST` to a URL you configure
in the Twilio console. The body is `application/x-www-form-urlencoded` (plain
HTML-form style), with fields like `From`, `To`, `Body`, `MessageSid`.

```
Patient's phone ──SMS──> Twilio ──POST /webhooks/sms/inbound──> this app
                                                                 │
Twilio <── TwiML response: <Response><Message>Confirmed!</Message> │
    │
    └──SMS──> Patient's phone
```

### TwiML — your response is a program

Your HTTP response isn't data, it's **instructions**: TwiML (Twilio Markup
Language), XML that tells Twilio what to do next — `<Message>` sends an SMS,
`<Say>` speaks on a call, `<Gather>` collects keypad input, `<Hangup>` ends
the call. The `twilio` Python SDK builds it for you
(`MessagingResponse`, `VoiceResponse`).

### The three flows in this repo

| Flow | Endpoint | Twilio sends | You return |
|---|---|---|---|
| Patient texts you | `POST /webhooks/sms/inbound` | `From`, `Body`, `MessageSid` | TwiML `<Message>` reply |
| Delivery tracking | `POST /webhooks/sms/status` | `MessageStatus` (`queued`/`sent`/`delivered`/`failed`), `ErrorCode` | `204` — informational only |
| Patient calls you | `POST /webhooks/voice/inbound` | `CallSid`, `From`, `CallStatus` | TwiML `<Gather>` + `<Say>` menu |
| IVR keypress | `POST /webhooks/voice/menu` | `Digits`, `CallSid` | TwiML `<Say>` + `<Hangup>` |

The voice flow shows the core pattern: **every IVR step is a fresh HTTP
call**. `<Gather action="/webhooks/voice/menu">` means "after collecting a
digit, POST it to that path" — your server is the state machine.

### Signature validation — proving it's really Twilio

Anyone who finds your webhook URL could POST fake "patient confirmed"
messages. So Twilio signs every request: `X-Twilio-Signature` is
`base64(HMAC-SHA1(auth_token, url + sorted_params))`. `app/security.py`
verifies it with the SDK's `RequestValidator` before any handler runs —
`403` on failure.

The catch: the signature covers **the exact URL Twilio called**, so the app
validates against `APP_BASE_URL + path`. Behind a tunnel/proxy that rewrites
the scheme (`https` → `http`) or host, validation breaks — that's the #1
real-world Twilio webhook bug. Set `APP_BASE_URL` to your public URL.

`scripts/simulate.py` computes the identical signature with
`TWILIO_AUTH_TOKEN` (default `local-dev-token` in `.env`), so validation is
exercised for real, not stubbed.

### Mock mode

`app/twilio_client.py` is the only file that would ever hit the Twilio API.
With `MOCK_MODE=true` (or no real credentials) `send_sms()` logs
`[MOCK] SMS -> ...` instead. Watch it fire when a patient replies `CONFIRM`.

## Layout

```
app/
  main.py            FastAPI app, mounts routers, /health
  config.py          pydantic-settings: TWILIO_* env vars, MOCK_MODE
  security.py        X-Twilio-Signature validation dependency
  companion.py       keyword → reply logic (the "patient brain")
  twilio_client.py   send_sms() — real Twilio API or [MOCK] log
  routers/sms.py     /webhooks/sms/inbound, /webhooks/sms/status
  routers/voice.py   /webhooks/voice/inbound, /webhooks/voice/menu
scripts/simulate.py  signed-payload replay CLI
tests/               pytest — keywords, callbacks, 403s, voice
```

## Going live — checklist

1. `ngrok http 8000` → copy the `https://...` URL.
2. Twilio console → your phone number → set webhooks:
   - *A message comes in* → `https://<ngrok>/webhooks/sms/inbound`
   - *A call comes in* → `https://<ngrok>/webhooks/voice/inbound`
3. `.env`: real `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
   `TWILIO_PHONE_NUMBER`, `APP_BASE_URL=https://<ngrok>`, `MOCK_MODE=false`.
4. For status callbacks on outbound sends, pass
   `status_callback="https://<ngrok>/webhooks/sms/status"` to
   `messages.create` in `app/twilio_client.py`.
5. Restart — the simulator still works (point `--url` at ngrok if you like).

## Extending toward a real companion app

- `companion.reply_for()` → look up the patient by `From` number, pull their
  real appointments/meds from a DB instead of `APPOINTMENT` canned text.
- Persist `MessageStatus` callbacks to flag patients whose reminders fail.
- `<Gather>` currently takes one digit; gather speech with `input="speech"`
  or chain menus for deeper IVR trees.
