import asyncio
from datetime import date
from queue import Queue
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from futures_research.api import create_app
from futures_research.llm import client as llm_client_module
from futures_research.main import run_research
from futures_research.scheduler import run_batch_research


class WebSocketEventTests(unittest.TestCase):
    def setUp(self):
        self.api_key_patcher = patch.object(llm_client_module.config, "ANTHROPIC_API_KEY", "")
        self.base_url_patcher = patch.object(llm_client_module.config, "ANTHROPIC_BASE_URL", "")
        self.api_key_patcher.start()
        self.base_url_patcher.start()
        self.client = TestClient(create_app())

    def tearDown(self):
        self.base_url_patcher.stop()
        self.api_key_patcher.stop()

    def _run_async_in_thread(self, coroutine_factory):
        outcome = Queue()

        def _runner():
            try:
                outcome.put(("result", asyncio.run(coroutine_factory())))
            except Exception as exc:  # pragma: no cover - exercised only on unexpected failures
                outcome.put(("error", exc))

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        return thread, outcome

    def _collect_until(self, websocket, stop_event_type: str):
        events = []
        while True:
            payload = websocket.receive_json()
            if payload["event_type"] == "subscribed":
                continue
            events.append(payload)
            if payload["event_type"] == stop_event_type:
                return events

    def test_single_run_websocket_broadcasts_workflow_events(self):
        with self.client.websocket_connect("/ws/events?channel=run") as websocket:
            thread, outcome = self._run_async_in_thread(lambda: run_research("CF", date(2026, 4, 1)))
            events = self._collect_until(websocket, "run_completed")

        thread.join(timeout=30)
        self.assertFalse(thread.is_alive(), "run_research thread did not finish in time")
        status, value = outcome.get_nowait()
        if status == "error":
            raise value

        event_types = [event["event_type"] for event in events]
        step_names = [event["step"] for event in events if event["event_type"] == "step_started"]

        self.assertEqual(events[0]["event_type"], "run_started")
        self.assertEqual(events[-1]["event_type"], "run_completed")
        self.assertIn("review_round_completed", event_types)
        self.assertTrue({"aggregate", "analyze", "write", "review"}.issubset(set(step_names)))
        self.assertEqual(events[0]["requested_symbol"], "CF")
        self.assertEqual(events[-1]["payload"]["passed"], value.review_result.passed)

    def test_batch_websocket_broadcasts_batch_events(self):
        with self.client.websocket_connect("/ws/events?channel=batch") as websocket:
            thread, outcome = self._run_async_in_thread(
                lambda: run_batch_research(["CF", "M"], date(2026, 4, 1), concurrency=2)
            )
            events = self._collect_until(websocket, "batch_completed")

        thread.join(timeout=30)
        self.assertFalse(thread.is_alive(), "run_batch_research thread did not finish in time")
        status, value = outcome.get_nowait()
        if status == "error":
            raise value

        event_types = [event["event_type"] for event in events]
        started_symbols = sorted(
            event["requested_symbol"] for event in events if event["event_type"] == "batch_item_started"
        )
        completed_symbols = sorted(
            event["requested_symbol"] for event in events if event["event_type"] == "batch_item_completed"
        )

        self.assertEqual(events[0]["event_type"], "batch_started")
        self.assertEqual(events[-1]["event_type"], "batch_completed")
        self.assertIn("batch_item_started", event_types)
        self.assertIn("batch_item_completed", event_types)
        self.assertEqual(started_symbols, ["CF", "M"])
        self.assertEqual(completed_symbols, ["CF", "M"])
        self.assertEqual(events[-1]["payload"]["total"], value.total)


if __name__ == "__main__":
    unittest.main()
