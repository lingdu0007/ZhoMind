from __future__ import annotations

import asyncio
from pathlib import Path

from src.application.interfaces.storage import DocumentStorage


class LocalStorage(DocumentStorage):
    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir).expanduser().resolve()

    async def save(self, *, key: str, content: bytes) -> str:
        target = self._resolve_target(key)
        await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(target.write_bytes, content)
        return str(target)

    async def read(self, path: str) -> bytes:
        target = self._resolve_existing(path)
        return await asyncio.to_thread(target.read_bytes)

    async def delete(self, path: str) -> None:
        target = self._resolve_existing(path)
        if not target.exists():
            return
        await asyncio.to_thread(target.unlink)
        await self._prune_empty_parents(target.parent)

    def _resolve_target(self, key: str) -> Path:
        relative = Path(key)
        target = (self._base_dir / relative).resolve()
        if self._base_dir not in target.parents and target != self._base_dir:
            raise ValueError("Invalid storage path")
        return target

    def _resolve_existing(self, path: str) -> Path:
        target = Path(path).expanduser().resolve()
        if self._base_dir not in target.parents and target != self._base_dir:
            raise ValueError("Invalid storage path")
        return target

    async def _prune_empty_parents(self, start: Path) -> None:
        current = start
        while current != self._base_dir and current.is_relative_to(self._base_dir):
            try:
                await asyncio.to_thread(current.rmdir)
            except OSError:
                return
            current = current.parent
