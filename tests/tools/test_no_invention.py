import pytest
from tests.conftest import FakeHttp, json_response, NOW_ISO
import gestnova_marketing.connectors.shopify  # noqa: F401
import gestnova_marketing.connectors.ga4       # noqa: F401
from gestnova_marketing.tools.reports import SalesTool, TrafficTool
from gestnova_marketing.credentials.store import Connection, InMemoryCredentialStore


def _store():
    s = InMemoryCredentialStore()
    s.save(Connection("c1", "shopify", "shop-1", "t", ["read_orders"], "active"))
    s.save(Connection("c1", "ga4", "properties/111", "t", ["analytics.readonly"], "active"))
    return s


@pytest.mark.asyncio
async def test_api_500_never_produces_metrics():
    tool = SalesTool(store=_store(), http=FakeHttp(lambda r: json_response({"e": 1}, status=500)),
                     now_iso=NOW_ISO)
    res = await tool.execute({"company_id": "c1", "start": "2026-05-26", "end": "2026-06-02"})
    assert res["status"] == "error"
    assert res["metrics"] == {}
    assert "500" in res["error"]


@pytest.mark.asyncio
async def test_empty_data_is_no_data_not_zero_invention():
    tool = TrafficTool(store=_store(),
                       http=FakeHttp(lambda r: json_response({"rows": [], "metricHeaders": []})),
                       now_iso=NOW_ISO)
    res = await tool.execute({"company_id": "c1", "start": "2026-05-26", "end": "2026-06-02"})
    assert res["status"] == "no_data"
    assert res["metrics"] == {}
    assert res["error"] is not None


@pytest.mark.asyncio
async def test_every_ok_result_has_source_and_range():
    tool = SalesTool(store=_store(),
                     http=FakeHttp(lambda r: json_response({"orders": [{"total_price": "1.00", "id": 1}]})),
                     now_iso=NOW_ISO)
    res = await tool.execute({"company_id": "c1", "start": "2026-05-26", "end": "2026-06-02"})
    assert res["source"] == "shopify"
    assert res["date_range"]["start"] == "2026-05-26"
    assert res["fetched_at"] == NOW_ISO
