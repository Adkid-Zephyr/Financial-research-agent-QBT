from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import date, datetime, timezone
from queue import Queue
from typing import Any, Dict, Iterator, Literal, Optional
from uuid import UUID, uuid4
import contextvars

from pydantic import BaseModel, Field

EventChannel = Literal["run", "batch"]
EventType = Literal[
    "run_started",
    "step_started",
    "review_round_completed",
    "run_completed",
    "run_failed",
    "batch_started",
    "batch_item_started",
    "batch_item_completed",
    "batch_item_failed",
    "batch_completed",
    "batch_failed",
]

_current_batch_id: contextvars.ContextVar[Optional[UUID]] = contextvars.ContextVar("current_batch_id", default=None)


class RuntimeEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    channel: EventChannel
    event_type: EventType
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: Optional[UUID] = None
    batch_id: Optional[UUID] = None
    requested_symbol: Optional[str] = None
    resolved_symbol: Optional[str] = None
    variety_code: Optional[str] = None
    variety: Optional[str] = None
    target_date: Optional[date] = None
    step: Optional[str] = None
    review_round: Optional[int] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class EventSubscription(BaseModel):
    subscription_id: UUID = Field(default_factory=uuid4)
    channel: Optional[EventChannel] = None
    run_id: Optional[UUID] = None
    batch_id: Optional[UUID] = None
    queue: Queue = Field(default_factory=Queue, exclude=True)

    model_config = {
        "arbitrary_types_allowed": True,
    }


class EventBus:
    def __init__(self):
        self._subscriptions: Dict[UUID, EventSubscription] = {}
        self._lock = threading.Lock()

    def subscribe(
        self,
        *,
        channel: Optional[EventChannel] = None,
        run_id: Optional[UUID] = None,
        batch_id: Optional[UUID] = None,
    ) -> EventSubscription:
        subscription = EventSubscription(channel=channel, run_id=run_id, batch_id=batch_id)
        with self._lock:
            self._subscriptions[subscription.subscription_id] = subscription
        return subscription

    def unsubscribe(self, subscription_id: UUID) -> None:
        with self._lock:
            self._subscriptions.pop(subscription_id, None)

    def publish(self, event: RuntimeEvent) -> None:
        with self._lock:
            subscriptions = list(self._subscriptions.values())
        for subscription in subscriptions:
            if self._matches(subscription, event):
                subscription.queue.put(event)

    def _matches(self, subscription: EventSubscription, event: RuntimeEvent) -> bool:
        if subscription.channel and subscription.channel != event.channel:
            return False
        if subscription.run_id and subscription.run_id != event.run_id:
            return False
        if subscription.batch_id and subscription.batch_id != event.batch_id:
            return False
        return True


_event_bus = EventBus()


def get_event_bus() -> EventBus:
    return _event_bus


def publish_event(**payload: Any) -> RuntimeEvent:
    event = RuntimeEvent.model_validate(payload)
    get_event_bus().publish(event)
    return event


@contextmanager
def batch_event_context(batch_id: UUID) -> Iterator[UUID]:
    token = _current_batch_id.set(batch_id)
    try:
        yield batch_id
    finally:
        _current_batch_id.reset(token)


def get_current_batch_id() -> Optional[UUID]:
    return _current_batch_id.get()
