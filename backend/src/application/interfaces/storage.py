from __future__ import annotations

from typing import Protocol


class DocumentStorage(Protocol):
    async def save(self, *, key: str, content: bytes) -> str: ...

    async def read(self, path: str) -> bytes: ...

    async def delete(self, path: str) -> None: ...
