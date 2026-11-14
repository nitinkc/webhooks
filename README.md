# webhooks-101

A local FastAPI playground that acts as both a webhook provider and receiver.
Use the browser UI to send signed events, inspect requests, and explore tampering,
duplicate deliveries, and retries. No external accounts or API keys required.

## Run locally

**Prerequisites:** Python 3.11+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
Run the following from the repository root:

```bash
uv sync
```

On first setup, copy `.env.example` to `.env` (skip this if `.env` already exists):

```bash
cp .env.example .env
```

Start the server:

```bash
uv run uvicorn app.main:app --reload
```

- **Playground:** <http://localhost:8000> — start with the valid, tampered, and
  replay experiments; then add subscribers and emit an event to watch retries.
- **API reference:** <http://localhost:8000/docs>
- **Health check:** <http://localhost:8000/health>

No separate frontend server or build is needed. Stop the server with `Ctrl+C`.
State is in memory and resets on restart, including automatic reloads.

### Optional command-line demo

With the server still running, open another terminal in the repository root:

```bash
uv run python scripts/demo.py
```

This registers healthy, flaky, and dead receivers, emits two events, and prints
the delivery attempts. See [Sending webhooks](docs/sending.md) for manual requests.

### Configuration

Edit `.env` and restart the server to apply changes:

| Variable | Default | Purpose |
| --- | --- | --- |
| `WEBHOOK_SECRET` | `dev-secret-change-me` | Shared signing and verification secret |
| `MAX_ATTEMPTS` | `4` | Total delivery attempts, including the first |
| `RETRY_DELAY_SECONDS` | `0.5` | Initial retry delay; doubles between retries |

If port 8000 is busy, add `--port 8002` to the server command and open that port.
For the CLI demo, use `WEBHOOKS_BASE_URL=http://localhost:8002 uv run python scripts/demo.py`.

## Documentation

```bash
uv run mkdocs serve -a 127.0.0.1:8001
```

Open <http://127.0.0.1:8001> alongside the playground, or browse the source guides:

- [Dashboard tour](docs/dashboard.md) and [hands-on exercises](docs/exercises.md)
- [Provider vs. subscriber](docs/concepts/roles.md) and [delivery anatomy](docs/concepts/anatomy.md)
- [Receiving](docs/receiving.md), [sending](docs/sending.md), and [signature security](docs/security.md)
- [Tunnels and real GitHub webhooks](docs/exposing.md)
- [Tools](docs/tools.md) and [webhooks vs. WebSockets vs. gRPC](docs/concepts/delivery-options.md)

## Verify

```bash
uv run pytest -q
uv run mkdocs build --strict
```

**Local learning only:** this app has unauthenticated management endpoints and
in-memory state. Use synthetic data; it is not a production webhook service.
