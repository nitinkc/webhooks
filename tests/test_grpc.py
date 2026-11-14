import queue
import threading
import time
from concurrent import futures

import grpc
import pytest

from eventbus import events_pb2, events_pb2_grpc
from server.server import EventBusServicer


@pytest.fixture
def stub():
    """A real gRPC server on an ephemeral port, per test."""
    servicer = EventBusServicer()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    events_pb2_grpc.add_EventBusServicer_to_server(servicer, server)
    port = server.add_insecure_port("localhost:0")
    server.start()
    channel = grpc.insecure_channel(f"localhost:{port}")
    yield events_pb2_grpc.EventBusStub(channel), servicer
    channel.close()
    server.stop(grace=0)


def _wait_for_subscribers(servicer, n=1):
    for _ in range(100):
        if len(servicer._subscribers) == n:
            return
        time.sleep(0.02)
    raise AssertionError("Subscribe stream(s) never registered")


def _listener(stream, received):
    try:
        for event in stream:
            received.put(event)
    except grpc.RpcError:  # stream cancelled at teardown
        pass


def test_send_event_returns_the_event(stub):
    stub_obj, _ = stub
    resp = stub_obj.SendEvent(
        events_pb2.SendEventRequest(type="order.created", data_json='{"order_id": 42}')
    )
    assert resp.event.type == "order.created"
    assert resp.event.id.startswith("evt_")
    assert resp.event.data_json == '{"order_id": 42}'
    assert resp.delivered_to == 0


def test_subscribe_streams_emitted_events(stub):
    stub_obj, servicer = stub
    received = queue.Queue()
    stream = stub_obj.Subscribe(events_pb2.SubscribeRequest())
    t = threading.Thread(target=_listener, args=(stream, received), daemon=True)
    t.start()
    _wait_for_subscribers(servicer)

    resp = stub_obj.SendEvent(events_pb2.SendEventRequest(type="demo.ping"))
    assert resp.delivered_to == 1

    event = received.get(timeout=5)
    assert event.type == "demo.ping"
    assert event.id == resp.event.id
    stream.cancel()
    t.join(timeout=5)


def test_send_event_fans_out_to_every_stream(stub):
    stub_obj, servicer = stub
    received = queue.Queue()
    streams = [stub_obj.Subscribe(events_pb2.SubscribeRequest()) for _ in range(2)]
    threads = [
        threading.Thread(target=_listener, args=(stream, received), daemon=True)
        for stream in streams
    ]
    for t in threads:
        t.start()
    _wait_for_subscribers(servicer, n=2)

    resp = stub_obj.SendEvent(events_pb2.SendEventRequest(type="demo.ping"))
    assert resp.delivered_to == 2
    assert received.get(timeout=5).type == "demo.ping"
    assert received.get(timeout=5).type == "demo.ping"
    for stream in streams:
        stream.cancel()
    for t in threads:
        t.join(timeout=5)
