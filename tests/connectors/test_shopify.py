import pytest
from tests.conftest import FakeHttp, json_response, NOW_ISO
from gestnova_marketing.connectors import get_connector
import gestnova_marketing.connectors.shopify  # noqa: F401  (registers connector)
from gestnova_marketing.credentials.store import Connection
from gestnova_marketing.types import QuerySpec


def _conn():
    return Connection("c1", "shopify", "shop-1", "tok-shopify", ["read_orders"], "active")


@pytest.mark.asyncio
async def test_sales_summary_aggregates_orders():
    def handler(request):
        assert "shop-1.myshopify.com" in str(request.url)
        assert request.headers["X-Shopify-Access-Token"] == "tok-shopify"
        return json_response({"orders": [
            {"total_price": "100.50", "id": 1},
            {"total_price": "49.50", "id": 2},
        ]})

    conn = get_connector("shopify", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="shopify", metrics=["total_sales", "orders"],
                  start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)

    assert res.status == "ok"
    assert res.source == "shopify"
    assert res.account_id == "shop-1"
    assert res.fetched_at == NOW_ISO
    assert res.metrics["orders"] == 2
    assert res.metrics["total_sales"] == 150.0


@pytest.mark.asyncio
async def test_no_orders_returns_no_data():
    def handler(request):
        return json_response({"orders": []})

    conn = get_connector("shopify", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="shopify", metrics=["total_sales"], start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)
    assert res.status == "no_data"
    assert res.metrics == {}
    assert res.error is not None


@pytest.mark.asyncio
async def test_api_error_returns_error_status():
    def handler(request):
        return json_response({"errors": "Not authorized"}, status=401)

    conn = get_connector("shopify", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="shopify", metrics=["total_sales"], start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)
    assert res.status == "error"
    assert "401" in res.error
