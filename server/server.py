"""A minimal event bus over gRPC.

Run:  uv run python -m server.server      (listens on :50051)
Then: uv run python -m client.demo

Two RPCs, the two shapes you'll use most:

  SendEvent  — unary RPC: one event in, one response back.

  Subscribe  — server-streaming RPC: the call itself is the
               subscription. Events flow back on the open stream.
               No callback URL, no signatures, no retry log: if the
               client is connected it gets the event; if it isn't,
               there is nothing to retry — the stream just ends.

Everything is in-memory — all a local demo needs.
"""

import queue
import uuid
from concurrent import futures
from datetime import datetime, timezone

import grpc

from eventbus import events_pb2, events_pb2_grpc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class EventBusServicer(events_pb2_grpc.EventBusServicer):
    def __init__(self) -> None:
        # Each subscriber gets a queue; SendEvent fans out onto all of them.
        self._subscribers: list[queue.Queue] = []
        self.sent: list[events_pb2.Event] = []

    def SendEvent(self, request, context):
        event = events_pb2.Event(
            id="evt_" + uuid.uuid4().hex[:12],
            type=request.type or "demo.ping",
            created_at=_now(),
            data_json=request.data_json,
        )
        self.sent.append(event)
        for q in list(self._subscribers):
            q.put(event)
        return events_pb2.SendEventResponse(event=event, delivered_to=len(self._subscribers))

    def Subscribe(self, request, context):
        q: queue.Queue = queue.Queue()
        self._subscribers.append(q)
        try:
            while context.is_active():
                try:
                    yield q.get(timeout=0.5)
                except queue.Empty:
                    continue
        finally:
            self._subscribers.remove(q)


def serve(port: int = 50051) -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    events_pb2_grpc.add_EventBusServicer_to_server(EventBusServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"EventBus gRPC server listening on :{port}")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
