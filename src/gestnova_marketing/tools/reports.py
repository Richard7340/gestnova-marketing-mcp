"""Report tools. Each builds a QuerySpec with preset metrics/dimensions and
delegates to MarketingService. On no connection / failure: explicit status,
never fabricated data (golden rule)."""
from __future__ import annotations
from typing import Any

from ._base import BaseTool
from gestnova_marketing.connectors import HttpClient
from gestnova_marketing.credentials.store import CredentialStore
from gestnova_marketing.service import MarketingService, NoConnectionError, NowIso
from gestnova_marketing.types import DataResult, DateRange, QuerySpec

_RANGE_PROPS = {
    "company_id": {"type": "string"},
    "start": {"type": "string", "format": "date"},
    "end": {"type": "string", "format": "date"},
}
_RANGE_REQUIRED = ["company_id", "start", "end"]


class _ServiceTool(BaseTool):
    def __init__(self, store: CredentialStore, http: HttpClient, *, now_iso: NowIso) -> None:
        self._svc = MarketingService(store=store, http=http, now_iso=now_iso)
        # now_iso may be a fixed str (tests) or a zero-arg callable (production).
        self._now_iso = now_iso

    def _now(self) -> str:
        return self._now_iso() if callable(self._now_iso) else self._now_iso

    async def _run(self, company_id: str, query: QuerySpec) -> dict[str, Any]:
        try:
            res = await self._svc.run_query(company_id, query)
        except NoConnectionError as exc:
            return DataResult(
                source=query.source,
                account_id="",            # unknown — no connection
                date_range=DateRange(start=query.start, end=query.end),
                fetched_at=self._now(),
                status="error",
                error=str(exc),
            ).to_dict()
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


class OverviewTool(_ServiceTool):
    name = "marketingOverview"
    description = ("Unified marketing overview for a date range across all connected sources. "
                  "Missing/failed sources are reported explicitly, never invented.")
    input_schema = {"type": "object", "properties": _RANGE_PROPS, "required": _RANGE_REQUIRED}

    _PRESETS = {
        "shopify": (["total_sales", "orders"], []),
        "ga4": (["sessions", "activeUsers"], ["sessionSource"]),
        "google_ads": (["cost", "clicks", "impressions"], []),
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for source, (metrics, dims) in self._PRESETS.items():
            q = QuerySpec(source=source, metrics=metrics, dimensions=dims,
                          start=args["start"], end=args["end"])
            try:
                res = await self._svc.run_query(args["company_id"], q)
                out[source] = res.to_dict()
            except NoConnectionError as exc:
                # Uniform envelope: same full DataResult shape as ok/connector-error.
                out[source] = DataResult(
                    source=source,
                    account_id="",
                    date_range=DateRange(start=args["start"], end=args["end"]),
                    fetched_at=self._now(),
                    status="error",
                    error=str(exc),
                ).to_dict()
        return {"status": "ok", "date_range": {"start": args["start"], "end": args["end"]},
                "sources": out}


class QueryTool(_ServiceTool):
    name = "marketingQuery"
    description = ("Flexible query: pick source, metrics, dimensions, date range, filters. "
                  "For custom cross-cuts not covered by the canned reports. "
                  "Filters (equality by dimension) are supported for GA4; "
                  "other sources reject non-empty filters.")
    input_schema = {
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "source": {"type": "string", "enum": ["shopify", "ga4", "google_ads"]},
            "metrics": {"type": "array", "items": {"type": "string"}},
            "dimensions": {"type": "array", "items": {"type": "string"}},
            "start": {"type": "string", "format": "date"},
            "end": {"type": "string", "format": "date"},
            "filters": {"type": "object"},
        },
        "required": ["company_id", "source", "metrics", "start", "end"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        q = QuerySpec(source=args["source"], metrics=args["metrics"],
                      dimensions=args.get("dimensions", []),
                      start=args["start"], end=args["end"],
                      filters=args.get("filters", {}))
        return await self._run(args["company_id"], q)
