# grpc-101

A minimal playground for learning **gRPC streaming** — the same toy flow
(*something happened → tell interested parties*) expressed as RPCs:

- `SendEvent` — a **unary** RPC: one event in, one response back.
- `Subscribe` — a **server-streaming** RPC: the open call *is* the
  subscription; events flow back down the stream as they happen.

No accounts, no credentials, everything runs locally on `:50051`.

> This repo is one of three sibling playgrounds. The webhook version lives
> in `../webhooks` (signed `POST`s with retries); the websocket version in
> `../websockets-101` (frames on an open socket).

## Quickstart

```bash
uv sync

# terminal 1 — the gRPC server
uv run python -m server.server        # listens on :50051

# terminal 2 — the client: open a Subscribe stream, send events
uv run python -m client.demo
```

Prefer a UI? Run a third process — a FastAPI bridge that proxies the
browser to gRPC (REST → `SendEvent`, WebSocket → `Subscribe`):

```bash
uv run python -m ui.web               # http://localhost:8090
```

Tests: `uv run pytest`.

**Full documentation** (MkDocs Material): `uv run mkdocs serve`.

## What gRPC is

gRPC is RPC over HTTP/2 with **Protocol Buffers** as the contract. You
write a `.proto` file declaring services and messages once; tooling
generates typed client and server code in every major language. On the
wire the payloads are compact binary protobuf, and HTTP/2 multiplexes
many calls over one connection.

The headline feature: RPCs aren't just request/response. Four shapes
exist —

| Shape | Signature | In this repo |
|---|---|---|
| **Unary** | `SendEvent(req) -> resp` | emit one event |
| **Server-streaming** | `Subscribe(req) -> stream Event` | the subscription |
| Client-streaming | `stream Req -> resp` | — |
| Bidirectional | `stream Req <-> stream Resp` | — |

## The subscription, reinvented

A webhook subscriber hands the provider a URL and waits for `POST`s. A
gRPC subscriber just calls `Subscribe` and holds the line — the streaming
response *is* the subscription, and it appears in the type signature:

```proto
rpc Subscribe(SubscribeRequest) returns (stream Event);
```

No callback URL, no signatures, no retry log: if the client is connected
it gets the event; if it isn't, the stream ends and the client
reconnects.

## Layout

```
eventbus/
  events.proto    EventBus contract — SendEvent (unary) + Subscribe (stream)
  events_pb2*.py  generated stubs — regen: uv run python -m grpc_tools.protoc -I. \
                    --python_out=. --grpc_python_out=. eventbus/events.proto
server/
  server.py       EventBusServicer — Queue-based fan-out, listens on :50051
client/
  demo.py         CLI client — opens a Subscribe stream, sends events
ui/
  web.py          FastAPI bridge — browser UI → gRPC client (UI on :8090)
  static/         index.html — single-page UI, no build step
tests/
  test_grpc.py    spins up a real server on an ephemeral port per test
docs/             MkDocs site — the gRPC guide + exercises
```
