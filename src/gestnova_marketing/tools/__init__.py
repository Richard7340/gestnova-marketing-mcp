"""Tool registry."""
from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from ._base import BaseTool
from gestnova_marketing.credentials.store import CredentialStore, InMemoryCredentialStore
from gestnova_marketing.credentials.encrypted_file import EncryptedFileCredentialStore


class _DefaultHttp:
    """Real async HTTP client used at runtime (tools accept any HttpClient in tests)."""
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)

    async def request(self, method, url, *, headers=None, params=None, json=None):
        return await self._client.request(method, url, headers=headers, params=params, json=json)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_store() -> CredentialStore:
    key = os.environ.get("MARKETING_CRED_KEY")
    path = os.environ.get("MARKETING_CRED_PATH")
    if key and path:
        return EncryptedFileCredentialStore(path=Path(path), key=key)
    return InMemoryCredentialStore()


class PingTool(BaseTool):
    name = "ping"
    description = "Health check — returns server status and version."
    input_schema = {"type": "object", "properties": {}, "required": []}

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        from gestnova_marketing import __version__
        return {"status": "ok", "version": __version__}


def get_all_tools() -> list[BaseTool]:
    from .connections import ConnectAccountTool, CompleteConnectionTool, ListConnectionsTool
    from .reports import SalesTool, TrafficTool, AdsTool

    store = _build_store()
    http = _DefaultHttp()
    now = _now_iso()
    return [
        PingTool(),
        ConnectAccountTool(store=store, http=http, now_iso=now),
        CompleteConnectionTool(store=store, http=http, now_iso=now),
        ListConnectionsTool(store=store, http=http, now_iso=now),
        SalesTool(store=store, http=http, now_iso=now),
        TrafficTool(store=store, http=http, now_iso=now),
        AdsTool(store=store, http=http, now_iso=now),
    ]
