"""MarketingService — the only path tools use to reach data.
Enforces tenant isolation: every operation is scoped to one company_id and can
ONLY use that company's stored credentials."""
from __future__ import annotations

from typing import Callable, Union

from gestnova_marketing.connectors import get_connector, HttpClient
from gestnova_marketing.credentials.store import CredentialStore
from gestnova_marketing.types import DataResult, QuerySpec

NowIso = Union[str, Callable[[], str]]


class NoConnectionError(Exception):
    """Raised when the company has no active connection for the requested source."""


class MarketingService:
    def __init__(self, store: CredentialStore, http: HttpClient, *, now_iso: NowIso) -> None:
        self._store = store
        self._http = http
        # now_iso may be a fixed str (tests) or a zero-arg callable (production,
        # so fetched_at reflects the actual fetch time per request).
        self._now_iso = now_iso

    def _now(self) -> str:
        return self._now_iso() if callable(self._now_iso) else self._now_iso

    async def run_query(self, company_id: str, query: QuerySpec) -> DataResult:
        conn = self._store.get(company_id, query.source)
        if conn is None or conn.status != "active":
            raise NoConnectionError(
                f"company {company_id} has no active {query.source} connection")
        connector = get_connector(query.source, self._http, now_iso=self._now())
        return await connector.fetch(conn, query)

    def list_connections(self, company_id: str) -> list[dict]:
        return [
            {"source": c.source, "account_id": c.account_id, "status": c.status,
             "scopes": c.scopes}
            for c in self._store.list_for_company(company_id)
        ]
