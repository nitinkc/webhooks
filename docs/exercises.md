# Exercises

Hands-on tasks, roughly in order of difficulty.

## 1. Extend the contract

Add a `ListEvents` unary RPC to `eventbus/events.proto` that returns
`EventBusServicer.sent`, regenerate the stubs (the `protoc` command is in
the `.proto` header), implement it in `server/server.py`, and call it
from `client/demo.py`.

**Concepts:** the proto → generate → implement loop is the entire gRPC
workflow. What did the compiler catch for you that a JSON-over-HTTP API
wouldn't?

## 2. Poke the server with grpcurl

[`grpcurl`](https://github.com/fullstorydev/grpcurl) is `curl` for gRPC.
It works two ways: pointing at `.proto` files directly, or via server
reflection.

```bash
# without reflection — hand it the proto
grpcurl -plaintext -import-path . -proto eventbus/events.proto \
  -d '{"type": "demo.ping", "data_json": "{}"}' \
  localhost:50051 eventbus.v1.EventBus/SendEvent
```

Try the same for `Subscribe` — what happens to the command? Why is a
streaming RPC awkward for a CLI tool?

**Bonus:** add `grpc reflection` support to `server/server.py`
(`pip install grpcio-reflection`, a few lines) so callers don't need the
`.proto` at all.

## 3. Watch a stream die

Run the server and `client/demo.py`, then kill the server while the
`Subscribe` stream is open.

**Question:** what does the client see — an exception, or silence? Wrap
the `stub.Subscribe(...)` loop in a retry: how long does it take to
notice the server is gone, and what does reconnecting cost (missed
events?).

## 4. Stream in the other direction

Add a client-streaming RPC `SendEvents(stream SendEventRequest) returns
(SendEventsResponse)` — many events in, one summary out. Regenerate,
implement, and call it with a generator that yields events slowly (one
per second).

**Concepts:** how is this different from calling `SendEvent` in a loop?
(One HTTP/2 stream vs many — where does the overhead go?)

## 5. Deadlines

gRPC calls carry explicit deadlines end to end. Call `SendEvent` with a
`timeout=` of 0.001s while a `Subscribe` stream is sleeping.

**Question:** what status code comes back? How does a deadline differ
from the retry-with-backoff a webhook provider does?
