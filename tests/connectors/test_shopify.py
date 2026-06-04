import httpx
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


@pytest.mark.asyncio
async def test_non_json_body_returns_error_status():
    def handler(request):
        return httpx.Response(200, content=b"<html>not json</html>",
                              headers={"content-type": "text/html"})

    conn = get_connector("shopify", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="shopify", metrics=["total_sales"], start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)
    assert res.status == "error"
    assert res.source == "shopify"
    assert res.account_id == "shop-1"
    assert "non-JSON" in res.error
    assert res.metrics == {}


@pytest.mark.asyncio
async def test_filters_are_rejected_without_network_call():
    """Honest rejection: shopify doesn't support filters, so a non-empty
    filters set must error out WITHOUT making the request."""
    def handler(request):
        raise AssertionError("network handler must not be called when filters are rejected")

    conn = get_connector("shopify", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="shopify", metrics=["total_sales", "orders"],
                  start="2026-05-26", end="2026-06-02", filters={"city": "Madrid"})
    res = await conn.fetch(_conn(), q)

    assert res.status == "error"
    assert "filters are not supported" in res.error
    assert res.metrics == {}


@pytest.mark.asyncio
async def test_unsupported_metrics_rejected_without_network_call():
    """Honest rejection: shopify only computes total_sales/orders. An
    unrequested metric must error WITHOUT making the request, never present
    sales as if 'refunds' were fulfilled."""
    def handler(request):
        raise AssertionError("network handler must not be called for unsupported metrics")

    conn = get_connector("shopify", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="shopify", metrics=["refunds"],
                  start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)

    assert res.status == "error"
    assert "unsupported" in res.error
    assert "refunds" in res.error
    assert res.metrics == {}


@pytest.mark.asyncio
async def test_malformed_total_price_contributes_zero():
    def handler(request):
        return json_response({"orders": [
            {"total_price": "100.50", "id": 1},
            {"total_price": None, "id": 2},
            {"total_price": "not-a-number", "id": 3},
            {"total_price": "49.50", "id": 4},
        ]})

    conn = get_connector("shopify", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="shopify", metrics=["total_sales", "orders"],
                  start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)

    assert res.status == "ok"
    assert res.metrics["orders"] == 4
    # bad orders (None, non-numeric) contribute 0.0; good orders sum to 150.0
    assert res.metrics["total_sales"] == 150.0
