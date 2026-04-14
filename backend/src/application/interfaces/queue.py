from __future__ import annotations

from typing import Protocol


class QueuePort(Protocol):
    async def enqueue(self, task_name: str, payload: dict) -> None: ...
