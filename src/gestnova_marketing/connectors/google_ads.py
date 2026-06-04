"""Google Ads connector — searchStream GAQL over the REST API.
account_id is the client customer id (e.g. "123-456-7890"). Requires a
developer token (Gestnova MCC) + login-customer-id from env."""
from __future__ import annotations
import os

from gestnova_marketing.connectors import register
from gestnova_marketing.connectors._base import Connector
from gestnova_marketing.credentials.store import Connection
from gestnova_marketing.types import DataResult, DateRange, QuerySpec

API_VERSION = "v17"

# GAQL field per normalized metric name.
_METRIC_FIELD = {
    "cost": "metrics.cost_micros",
    "clicks": "metrics.clicks",
    "impressions": "metrics.impressions",
}


def _to_int(v) -> int:
    """Coerce a (possibly string) metric value to int; malformed -> 0, never raise."""
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


@register("google_ads")
class GoogleAdsConnector(Connector):
    async def fetch(self, conn: Connection, query: QuerySpec) -> DataResult:
        dr = DateRange(start=query.start, end=query.end)
        base = {"source": "google_ads", "account_id": conn.account_id,
                "date_range": dr, "fetched_at": self._now}

        if query.filters:  # honest: don't silently ignore unsupported filters
            return DataResult(**base, status="error",
                              error="filters are not supported for the google_ads connector in v1")

        dev_token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
        if not dev_token:
            return DataResult(**base, status="error",
                              error="missing Google Ads developer token (GOOGLE_ADS_DEVELOPER_TOKEN)")
        known = [m for m in query.metrics if m in _METRIC_FIELD]
        if not known:
            return DataResult(**base, status="error",
                              error=f"no supported Google Ads metrics in {query.metrics}; "
                                    f"supported: {sorted(_METRIC_FIELD)}")

        login_cid = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")
        customer_id = conn.account_id.replace("-", "")

        fields = ", ".join(_METRIC_FIELD[m] for m in known)
        gaql = (f"SELECT {fields} FROM customer "
                f"WHERE segments.date BETWEEN '{query.start}' AND '{query.end}'")
        url = (f"https://googleads.googleapis.com/{API_VERSION}/"
               f"customers/{customer_id}/googleAds:searchStream")
        headers = {
            "Authorization": f"Bearer {conn.token}",
            "developer-token": dev_token,
        }
        if login_cid:
            headers["login-customer-id"] = login_cid

        try:
            resp = await self._http.request("POST", url, headers=headers, json={"query": gaql})
        except Exception as exc:  # network failure — never fabricate
            return DataResult(**base, status="error", error=f"request failed: {exc}")

        if resp.status_code != 200:
            return DataResult(**base, status="error",
                              error=f"google_ads HTTP {resp.status_code}: {resp.text[:200]}")

        # searchStream returns a list of batches, each with "results".
        try:
            batches = resp.json()
        except Exception as exc:  # 200 with a non-JSON body — never fabricate
            return DataResult(**base, status="error",
                              error=f"google_ads returned non-JSON body: {exc}")

        results = [r for b in batches for r in b.get("results", [])]
        if not results:
            return DataResult(**base, status="no_data",
                              error="google_ads returned 0 rows for the range")

        totals = {m: 0 for m in known}
        for r in results:
            m = r.get("metrics", {})
            if "cost" in totals:
                totals["cost"] += _to_int(m.get("costMicros", 0))
            if "clicks" in totals:
                totals["clicks"] += _to_int(m.get("clicks", 0))
            if "impressions" in totals:
                totals["impressions"] += _to_int(m.get("impressions", 0))
        if "cost" in totals:
            totals["cost"] = round(totals["cost"] / 1_000_000, 2)  # micros -> currency

        return DataResult(**base, status="ok", metrics=totals)
