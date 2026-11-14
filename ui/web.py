"""Browser UI for the EventBus — a thin HTTP/WebSocket bridge to gRPC.

Browsers can't speak gRPC/HTTP2 natively, so this app sits in between:

    browser --HTTP-->  POST /api/events   --SendEvent-->   gRPC server :50051
    browser <--WS--    /ws/subscribe      <--Subscribe--   gRPC server :50051

Run the gRPC server first, then this bridge:

    uv run python -m server.server        # gRPC on :50051
    uv run python -m ui.web               # UI on http://localhost:8090
"""

import asyncio
import queue
import threading
from pathlib import Path

import grpc
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel

from eventbus import events_pb2, events_pb2_grpc

GRPC_ADDR = "localhost:50051"
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="grpc-101 EventBus UI")


def _stub() -> events_pb2_grpc.EventBusStub:
    return events_pb2_grpc.EventBusStub(grpc.insecure_channel(GRPC_ADDR))


def _event_to_dict(e: events_pb2.Event) -> dict:
    return {"id": e.id, "type": e.type, "created_at": e.created_at, "data_json": e.data_json}


class EventIn(BaseModel):
    type: str = "demo.ping"
    data_json: str = "{}"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict:
    """Is the gRPC server reachable? Drives the UI's status indicator."""
    channel = grpc.insecure_channel(GRPC_ADDR)
    try:
        grpc.channel_ready_future(channel).result(timeout=1.5)
        return {"grpc": "connected", "addr": GRPC_ADDR}
    except grpc.FutureTimeoutError:
        return {"grpc": "unreachable", "addr": GRPC_ADDR}


@app.post("/api/events")
def send_event(body: EventIn) -> dict:
    """Unary bridge: one POST -> one SendEvent RPC."""
    try:
        resp = _stub().SendEvent(
            events_pb2.SendEventRequest(type=body.type, data_json=body.data_json),
            timeout=5,
        )
    except grpc.RpcError as exc:
        return {"ok": False, "error": f"{exc.code().name}: {exc.details()}"}
    return {"ok": True, "event": _event_to_dict(resp.event), "delivered_to": resp.delivered_to}


@app.websocket("/ws/subscribe")
async def subscribe(ws: WebSocket) -> None:
    """Streaming bridge: the WebSocket lifetime mirrors the Subscribe call."""
    await ws.accept()
    loop = asyncio.get_running_loop()
    inbox: queue.Queue = queue.Queue()
    call = _stub().Subscribe(events_pb2.SubscribeRequest())

    def pump() -> None:
        try:
            for event in call:
                loop.call_soon_threadsafe(inbox.put, _event_to_dict(event))
        except grpc.RpcError:
            loop.call_soon_threadsafe(inbox.put, None)

    thread = threading.Thread(target=pump, daemon=True)
    thread.start()
    try:
        while True:
            item = await loop.run_in_executor(None, inbox.get)
            if item is None:
                await ws.close(code=1011)
                return
            await ws.send_json(item)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        call.cancel()


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8090)


if __name__ == "__main__":
    main()
