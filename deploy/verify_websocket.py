from __future__ import annotations

import argparse
import asyncio
import json

import websockets


async def _run(url: str, expect: int, timeout: float) -> None:
    async with websockets.connect(url, open_timeout=timeout) as websocket:
        for index in range(expect):
            message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
            payload = json.loads(message)
            print("[%d] %s" % (index + 1, json.dumps(payload, ensure_ascii=False)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify WebSocket subscriptions against the deployed stack.")
    parser.add_argument("--url", required=True, help="WebSocket URL, e.g. ws://nginx/ws/events?channel=run")
    parser.add_argument("--expect", type=int, default=1, help="How many messages to read before exiting")
    parser.add_argument("--timeout", type=float, default=15.0, help="Seconds to wait for each message")
    args = parser.parse_args()
    asyncio.run(_run(args.url, args.expect, args.timeout))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
