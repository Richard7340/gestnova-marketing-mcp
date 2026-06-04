"""GA4 connector — Data API v1 runReport. account_id is the GA4 property
resource name, e.g. "properties/111". Token is an OAuth access token."""
from __future__ import annotations

from gestnova_marketing.connectors import register
from gestnova_marketing.connectors._base import Connector
from gestnova_marketing.credentials.store import Connection
from gestnova_marketing.types import DataResult, DateRange, QuerySpec


@register("ga4")
class GA4Connector(Connector):
    async def fetch(self, conn: Connection, query: QuerySpec) -> DataResult:
        dr = DateRange(start=query.start, end=query.end)
        base = {"source": "ga4", "account_id": conn.account_id,
                "date_range": dr, "fetched_at": self._now}
        url = f"https://analyticsdata.googleapis.com/v1beta/{conn.account_id}:runReport"
        body = {
            "dateRanges": [{"startDate": query.start, "endDate": query.end}],
            "metrics": [{"name": m} for m in query.metrics],
            "dimensions": [{"name": d} for d in query.dimensions],
        }
        headers = {"Authorization": f"Bearer {conn.token}"}
        try:
            resp = await self._http.request("POST", url, headers=headers, json=body)
        except Exception as exc:  # network failure — never fabricate
            return DataResult(**base, status="error", error=f"request failed: {exc}")

        if resp.status_code != 200:
            return DataResult(**base, status="error",
                              error=f"ga4 HTTP {resp.status_code}: {resp.text[:200]}")

        try:
            payload = resp.json()
        except Exception as exc:  # 200 with a non-JSON body — never fabricate
            return DataResult(**base, status="error",
                              error=f"ga4 returned non-JSON body: {exc}")

        rows = payload.get("rows", [])
        if not rows:
            return DataResult(**base, status="no_data",
                              error="ga4 returned 0 rows for the range")

        def _to_num(v):
            try:
                f = float(v)
            except (TypeError, ValueError):
                return 0
            return int(f) if f.is_integer() else f

        try:
            metric_names = [h["name"] for h in payload.get("metricHeaders", [])]
            dim_names = [h["name"] for h in payload.get("dimensionHeaders", [])]

            totals = {m: 0 for m in metric_names}
            out_rows: list[dict] = []
            for r in rows:
                row: dict = {}
                for i, dv in enumerate(r.get("dimensionValues", [])):
                    row[dim_names[i]] = dv.get("value")
                for i, mv in enumerate(r.get("metricValues", [])):
                    val = _to_num(mv.get("value"))
                    row[metric_names[i]] = val
                    totals[metric_names[i]] += val
                out_rows.append(row)
        except Exception as exc:  # malformed structure — never fabricate
            return DataResult(**base, status="error",
                              error=f"ga4 response parse failed: {exc}")

        return DataResult(**base, status="ok", metrics=totals, rows=out_rows)
