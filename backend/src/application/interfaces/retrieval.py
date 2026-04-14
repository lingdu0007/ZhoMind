from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class RetrievalResult:
    chunks: list[dict[str, Any]]
    trace: dict[str, Any]


class RetrievalPort(Protocol):
    async def retrieve(
        self,
        query: str,
        *,
        user_id: str,
        document_ids: list[str] | None = None,
        version: int | None = None,
    ) -> RetrievalResult: ...
