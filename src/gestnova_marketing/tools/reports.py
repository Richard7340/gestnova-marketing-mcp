"""Report tools. Each builds a QuerySpec with preset metrics/dimensions and
delegates to MarketingService. On no connection / failure: explicit status,
never fabricated data (golden rule)."""
from __future__ import annotations
from typing import Any

from ._base import BaseTool
from gestnova_marketing.connectors import HttpClient
from gestnova_marketing.credentials.store import CredentialStore
from gestnova_marketing.service import MarketingService, NoConnectionError
from gestnova_marketing.types import QuerySpec

_RANGE_PROPS = {
    "company_id": {"type": "string"},
    "start": {"type": "string", "format": "date"},
    "end": {"type": "string", "format": "date"},
}
_RANGE_REQUIRED = ["company_id", "start", "end"]


class _ServiceTool(BaseTool):
    def __init__(self, store: CredentialStore, http: HttpClient, *, now_iso: str) -> None:
        self._svc = MarketingService(store=store, http=http, now_iso=now_iso)

    async def _run(self, company_id: str, query: QuerySpec) -> dict[str, Any]:
        try:
            res = await self._svc.run_query(company_id, query)
        except NoConnectionError as exc:
            return {"status": "error", "error": str(exc)}
        return res.to_dict()


class SalesTool(_ServiceTool):
    name = "marketingSales"
    description = "Shopify sales for a date range (total_sales, orders). Numbers are live and carry source + range."
    input_schema = {"type": "object", "properties": _RANGE_PROPS, "required": _RANGE_REQUIRED}

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        q = QuerySpec(source="shopify", metrics=["total_sales", "orders"],
                      start=args["start"], end=args["end"])
        return await self._run(args["company_id"], q)


class TrafficTool(_ServiceTool):
    name = "marketingTraffic"
    description = "GA4 traffic for a date range (sessions, activeUsers by source). Live, with source + range."
    input_schema = {"type": "object", "properties": _RANGE_PROPS, "required": _RANGE_REQUIRED}

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        q = QuerySpec(source="ga4", metrics=["sessions", "activeUsers"],
                      dimensions=["sessionSource"], start=args["start"], end=args["end"])
        return await self._run(args["company_id"], q)


class AdsTool(_ServiceTool):
    name = "marketingAds"
    description = "Google Ads performance for a date range (cost, clicks, impressions). Live, with source + range."
    input_schema = {"type": "object", "properties": _RANGE_PROPS, "required": _RANGE_REQUIRED}

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        q = QuerySpec(source="google_ads", metrics=["cost", "clicks", "impressions"],
                      start=args["start"], end=args["end"])
        return await self._run(args["company_id"], q)
