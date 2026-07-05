"""Minimal in-process WebSocket broadcast hub for the live Exercise feed.

Clients subscribe per-scenario; the engine publishes log/event/topology updates.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class Hub:
    def __init__(self) -> None:
        self._clients: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, scenario_id: int, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients[scenario_id].add(ws)

    async def disconnect(self, scenario_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._clients[scenario_id].discard(ws)

    async def publish(self, scenario_id: int, message: dict) -> None:
        async with self._lock:
            targets = list(self._clients.get(scenario_id, ()))
        dead = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients[scenario_id].discard(ws)


hub = Hub()
