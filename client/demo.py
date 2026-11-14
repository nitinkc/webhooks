#!/usr/bin/env python3
"""The gRPC lifecycle in one command.

Prerequisite — the gRPC server must be running:

    uv run python -m server.server      (listens on :50051)

This script then:
  1. opens a Subscribe stream in the background — the subscription
  2. calls SendEvent twice — emitting events
  3. prints what the stream delivered back

The subscription here is a streaming call the client holds open — no
callback URL, no signatures, no retries.
"""

import threading
import time

import grpc

from eventbus import events_pb2, events_pb2_grpc

ADDR = "localhost:50051"


def listen(stub: events_pb2_grpc.EventBusStub, label: str) -> None:
    """One subscriber: the stream is the subscription."""
    for event in stub.Subscribe(events_pb2.SubscribeRequest()):
        print(f"    {label} <- {event.type} ({event.id}) at {event.created_at}")


def main() -> None:
    channel = grpc.insecure_channel(ADDR)
    try:
        grpc.channel_ready_future(channel).result(timeout=5)
    except grpc.FutureTimeoutError:
        sys.exit(f"gRPC server not reachable at {ADDR} — start it with: uv run python -m server.server")
    stub = events_pb2_grpc.EventBusStub(channel)

    print("1. Opening a Subscribe stream (the gRPC subscription)...")
    t = threading.Thread(target=listen, args=(stub, "subscriber"), daemon=True)
    t.start()
    time.sleep(0.3)  # let the stream reach the server

    print("\n2. Sending events via the SendEvent unary RPC...")
    for event_type, data in (
        ("demo.ping", '{"hello": "world"}'),
        ("order.created", '{"order_id": 42, "total": "9.99"}'),
    ):
        resp = stub.SendEvent(events_pb2.SendEventRequest(type=event_type, data_json=data))
        print(f"   sent {event_type:<14} -> delivered to {resp.delivered_to} stream(s)")

    print("\n3. What the stream delivered (above) — no retries, no signatures:")
    time.sleep(0.5)
    print("\nDone — the same two events exist in the webhook demo; compare the transports.")


if __name__ == "__main__":
    main()
