# Open-source tools for learning and running webhooks

## For demoing / inspecting

| Tool | What it is | Use it to |
|---|---|---|
| **webhook.site** | Instant public endpoint showing every request — headers, body, signature. Open source, self-hostable via Docker | See what a provider's delivery looks like without writing a receiver |
| **localtunnel** | OSS tunnel; `npx localtunnel --port 8000`, no signup | Put localhost on a public URL so real providers can reach you |
| **zrok** | OSS sharing platform with a free hosted tier | Same as localtunnel, more features (private shares) |
| **bore** | Minimal OSS TCP tunnel (Rust) | Self-host your own relay for zero third-party dependency |
| **ngrok** | The industry default tunnel (closed source, needs account) | Same role; worth knowing since every provider's docs mention it |
| **RequestBin variants** | Self-hosted request inspectors | webhook.site equivalent inside your own infra |

## For building a real provider

| Tool | What it is |
|---|---|
| **Svix** ([github.com/svix/svix](https://github.com/svix/svix)) | Open-source "webhooks as a service" — the production version of `app/dispatcher.py`: queues, retries, per-endpoint secrets, delivery logs, endpoint auto-disable. Run it instead of building your own. |
| **Standard Webhooks** ([standardwebhooks.com](https://www.standardwebhooks.com)) | The open spec this repo follows (authored by ngrok, Svix, Twilio, …): `webhook-id`/`webhook-timestamp`/`webhook-signature` headers + HMAC-SHA256. Client libraries exist for most languages. |

## For testing receivers

| Tool | Use |
|---|---|
| `scripts/send.py` (this repo) | One signed `POST` to any URL — the 30-line essence of a provider |
| `curl` | Forge payloads by hand: compute `openssl dgst -sha256 -hmac "$SECRET"` and set the header yourself |
| **httpie** | Friendlier CLI than curl for poking endpoints |
| **pytest + TestClient** | This repo's `tests/` show the pattern: sign in the test, assert verify/dedupe/retry |

## Which should I reach for when?

- *"Show me what GitHub actually sends"* → webhook.site as the Payload URL.
- *"Let GitHub reach my laptop"* → localtunnel + `/webhooks/receive`.
- *"I need to offer webhooks to my users"* → adopt Standard Webhooks, or run Svix rather than writing a dispatcher.
- *"Teach me the mechanics"* → this repo + `scripts/send.py` + the [exercises](exercises.md).
