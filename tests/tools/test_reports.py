import pytest
from tests.conftest import FakeHttp, json_response, NOW_ISO
import gestnova_marketing.connectors.shopify  # noqa: F401
import gestnova_marketing.connectors.ga4       # noqa: F401
from gestnova_marketing.tools.reports import SalesTool, TrafficTool
from gestnova_marketing.credentials.store import Connection, InMemoryCredentialStore


def _store():
    s = InMemoryCredentialStore()
    s.save(Connection("c1", "shopify", "shop-1", "tok-s", ["read_orders"], "active"))
    s.save(Connection("c1", "ga4", "properties/111", "tok-g", ["analytics.readonly"], "active"))
    return s


@pytest.mark.asyncio
async def test_sales_tool_returns_metadata_and_total():
    def handler(request):
        return json_response({"orders": [{"total_price": "200.00", "id": 1}]})
    tool = SalesTool(store=_store(), http=FakeHttp(handler), now_iso=NOW_ISO)
    res = await tool.execute({"company_id": "c1", "start": "2026-05-26", "end": "2026-06-02"})
    assert res["status"] == "ok"
    assert res["source"] == "shopify"
    assert res["metrics"]["total_sales"] == 200.0
    assert res["date_range"] == {"start": "2026-05-26", "end": "2026-06-02"}
    assert res["fetched_at"] == NOW_ISO


@pytest.mark.asyncio
async def test_traffic_tool_default_dimensions():
    def handler(request):
        return json_response({
            "rows": [{"dimensionValues": [{"value": "google"}],
                      "metricValues": [{"value": "50"}, {"value": "40"}]}],
            "metricHeaders": [{"name": "sessions"}, {"name": "activeUsers"}],
            "dimensionHeaders": [{"name": "sessionSource"}],
        })
    tool = TrafficTool(store=_store(), http=FakeHttp(handler), now_iso=NOW_ISO)
    res = await tool.execute({"company_id": "c1", "start": "2026-05-26", "end": "2026-06-02"})
    assert res["status"] == "ok"
    assert res["metrics"]["sessions"] == 50


@pytest.mark.asyncio
async def test_sales_tool_without_connection_reports_error_not_invention():
    tool = SalesTool(store=InMemoryCredentialStore(), http=FakeHttp(lambda r: json_response({})),
                     now_iso=NOW_ISO)
    res = await tool.execute({"company_id": "nope", "start": "2026-05-26", "end": "2026-06-02"})
    assert res["status"] == "error"
    assert "connection" in res["error"].lower()
    # Normalized error envelope: same shape as a DataResult error.
    assert res["metrics"] == {}
    assert res["metrics"] in ({}, None)
    assert res["rows"] == []
    assert res["source"] == "shopify"
    assert res["account_id"] == ""
    assert res["date_range"] == {"start": "2026-05-26", "end": "2026-06-02"}
    assert res["fetched_at"] == NOW_ISO


@pytest.mark.asyncio
async def test_overview_combines_available_sources():
    def handler(request):
        if "myshopify.com" in str(request.url):
            return json_response({"orders": [{"total_price": "100.00", "id": 1}]})
        if "runReport" in str(request.url):
            return json_response({
                "rows": [{"dimensionValues": [{"value": "google"}],
                          "metricValues": [{"value": "70"}]}],
                "metricHeaders": [{"name": "sessions"}],
                "dimensionHeaders": [{"name": "sessionSource"}],
            })
        return json_response({}, status=404)

    from gestnova_marketing.tools.reports import OverviewTool
    tool = OverviewTool(store=_store(), http=FakeHttp(handler), now_iso=NOW_ISO)
    res = await tool.execute({"company_id": "c1", "start": "2026-05-26", "end": "2026-06-02"})
    assert res["status"] == "ok"
    # Per-source results present; missing google_ads is reported, not invented.
    assert res["sources"]["shopify"]["metrics"]["total_sales"] == 100.0
    assert res["sources"]["ga4"]["metrics"]["sessions"] == 70
    # google_ads has no connection here -> full uniform envelope, not stripped.
    ga = res["sources"]["google_ads"]
    assert ga["status"] in ("error", "no_data")
    assert ga["source"] == "google_ads"
    assert ga["date_range"] == {"start": "2026-05-26", "end": "2026-06-02"}
    assert "fetched_at" in ga
    assert ga["metrics"] == {}


@pytest.mark.asyncio
async def test_query_tool_passes_through_custom_metrics():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        return json_response({
            "rows": [{"dimensionValues": [{"value": "Madrid"}],
                      "metricValues": [{"value": "12"}]}],
            "metricHeaders": [{"name": "conversions"}],
            "dimensionHeaders": [{"name": "city"}],
        })

    from gestnova_marketing.tools.reports import QueryTool
    tool = QueryTool(store=_store(), http=FakeHttp(handler), now_iso=NOW_ISO)
    res = await tool.execute({
        "company_id": "c1", "source": "ga4",
        "metrics": ["conversions"], "dimensions": ["city"],
        "start": "2026-05-26", "end": "2026-06-02",
    })
    assert res["status"] == "ok"
    assert res["rows"][0]["city"] == "Madrid"
    assert res["rows"][0]["conversions"] == 12
