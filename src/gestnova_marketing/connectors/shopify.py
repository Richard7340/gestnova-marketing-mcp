"""Shopify connector — sales/orders for a date range.
Docs: Admin REST API GET /admin/api/<ver>/orders.json"""
from __future__ import annotations

from gestnova_marketing.connectors import register
from gestnova_marketing.connectors._base import Connector
from gestnova_marketing.credentials.store import Connection
from gestnova_marketing.types import DataResult, DateRange, QuerySpec

API_VERSION = "2024-04"


@register("shopify")
class ShopifyConnector(Connector):
    async def fetch(self, conn: Connection, query: QuerySpec) -> DataResult:
        dr = DateRange(start=query.start, end=query.end)
        base = {"source": "shopify", "account_id": conn.account_id,
                "date_range": dr, "fetched_at": self._now}
        url = f"https://{conn.account_id}.myshopify.com/admin/api/{API_VERSION}/orders.json"
        params = {
            "status": "any",
            "created_at_min": f"{query.start}T00:00:00Z",
            "created_at_max": f"{query.end}T23:59:59Z",
            "limit": 250,
        }
        headers = {"X-Shopify-Access-Token": conn.token}
        try:
            resp = await self._http.request("GET", url, headers=headers, params=params)
        except Exception as exc:  # network failure — never fabricate
            return DataResult(**base, status="error", error=f"request failed: {exc}")

        if resp.status_code != 200:
            return DataResult(**base, status="error",
                              error=f"shopify HTTP {resp.status_code}: {resp.text[:200]}")

        orders = resp.json().get("orders", [])
        if not orders:
            return DataResult(**base, status="no_data",
                              error="shopify returned 0 orders for the range")

        total = round(sum(float(o.get("total_price", 0)) for o in orders), 2)
        return DataResult(**base, status="ok",
                          metrics={"orders": len(orders), "total_sales": total},
                          rows=[{"id": o.get("id"), "total_price": o.get("total_price")} for o in orders])
