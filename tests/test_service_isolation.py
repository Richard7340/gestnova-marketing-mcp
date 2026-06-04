import pytest
from tests.conftest import FakeHttp, json_response, NOW_ISO
import gestnova_marketing.connectors.shopify  # noqa: F401
from gestnova_marketing.service import MarketingService, NoConnectionError
from gestnova_marketing.types import QuerySpec


def _shopify_ok_handler(request):
    return json_response({"orders": [{"total_price": "10.00", "id": 1}]})


@pytest.mark.asyncio
async def test_runs_query_for_connected_company(store):
    svc = MarketingService(store=store, http=FakeHttp(_shopify_ok_handler), now_iso=NOW_ISO)
    q = QuerySpec(source="shopify", metrics=["total_sales"], start="2026-05-26", end="2026-06-02")
    res = await svc.run_query("c1", q)
    assert res.status == "ok"
    assert res.account_id == "shop-1"  # c1's shop, never c2's


@pytest.mark.asyncio
async def test_company_without_connection_raises(store):
    svc = MarketingService(store=store, http=FakeHttp(_shopify_ok_handler), now_iso=NOW_ISO)
    q = QuerySpec(source="ga4", metrics=["sessions"], start="2026-05-26", end="2026-06-02")
    # c2 has no ga4 connection -> must refuse, never fall back to another company
    with pytest.raises(NoConnectionError):
        await svc.run_query("c2", q)


@pytest.mark.asyncio
async def test_isolation_uses_only_callers_token(store):
    seen_tokens = []

    def handler(request):
        seen_tokens.append(request.headers.get("X-Shopify-Access-Token"))
        return json_response({"orders": [{"total_price": "5.00", "id": 9}]})

    svc = MarketingService(store=store, http=FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="shopify", metrics=["total_sales"], start="2026-05-26", end="2026-06-02")
    await svc.run_query("c2", q)
    assert seen_tokens == ["tok-other"]  # c2's token only, never c1's


@pytest.mark.asyncio
async def test_list_connections_is_company_scoped(store):
    svc = MarketingService(store=store, http=FakeHttp(_shopify_ok_handler), now_iso=NOW_ISO)
    conns = svc.list_connections("c2")
    assert [c["source"] for c in conns] == ["shopify"]
    assert all(c["account_id"] != "shop-1" for c in conns)
