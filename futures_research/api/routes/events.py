from __future__ import annotations

import asyncio
from queue import Empty
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from futures_research.events import EventChannel, EventBus, get_event_bus

router = APIRouter()


def _get_event_bus(websocket: WebSocket) -> EventBus:
    return getattr(websocket.app.state, "event_bus", get_event_bus())


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await websocket.accept()
    channel_param = websocket.query_params.get("channel")
    run_id_param = websocket.query_params.get("run_id")
    batch_id_param = websocket.query_params.get("batch_id")
    channel = channel_param if channel_param in {"run", "batch"} else None
    run_id = UUID(run_id_param) if run_id_param else None
    batch_id = UUID(batch_id_param) if batch_id_param else None
    event_bus = _get_event_bus(websocket)
    subscription = event_bus.subscribe(channel=channel, run_id=run_id, batch_id=batch_id)
    await websocket.send_json(
        {
            "event_type": "subscribed",
            "channel": channel or "all",
            "run_id": str(run_id) if run_id is not None else None,
            "batch_id": str(batch_id) if batch_id is not None else None,
        }
    )
    try:
        while True:
            if websocket.client_state == WebSocketState.DISCONNECTED:
                break
            try:
                event = subscription.queue.get_nowait()
            except Empty:
                try:
                    await asyncio.sleep(0.05)
                except asyncio.CancelledError:
                    break
                continue
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        event_bus.unsubscribe(subscription.subscription_id)
