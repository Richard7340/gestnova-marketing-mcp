"""Connector base + injectable async HTTP client protocol."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Protocol

import httpx

from gestnova_marketing.credentials.store import Connection
from gestnova_marketing.types import DataResult, QuerySpec


class HttpClient(Protocol):
    async def request(self, method: str, url: str, *,
                      headers: dict[str, str] | None = None,
                      params: dict[str, Any] | None = None,
                      json: dict[str, Any] | None = None) -> httpx.Response: ...


class Connector(ABC):
    source: str

    def __init__(self, http: HttpClient, *, now_iso: str) -> None:
        """now_iso is injected (the fetched_at stamp) so results are deterministic in tests."""
        self._http = http
        self._now = now_iso

    @abstractmethod
    async def fetch(self, conn: Connection, query: QuerySpec) -> DataResult: ...
