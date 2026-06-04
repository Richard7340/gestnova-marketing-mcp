import pytest
from tests.conftest import FakeHttp, json_response, NOW_ISO
import gestnova_marketing.connectors.shopify  # noqa: F401
from gestnova_marketing.credentials.store import Connection, InMemoryCredentialStore
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


def test_list_connections_never_exposes_token(store):
    # list_connections is the one place a tool could accidentally receive a
    # credential — assert tokens never leak through it.
    svc = MarketingService(store=store, http=FakeHttp(_shopify_ok_handler), now_iso=NOW_ISO)
    conns = svc.list_connections("c1")
    assert conns  # c1 has shopify/ga4/google_ads preloaded
    known_tokens = {"tok-shopify", "tok-ga4", "tok-ads"}
    for c in conns:
        assert "token" not in c
        assert not (known_tokens & {v for v in c.values() if isinstance(v, str)})


def _raise_if_hit(request):
    raise AssertionError("network must not be called for an inactive connection")


@pytest.mark.parametrize("status", ["revoked", "expired"])
@pytest.mark.asyncio
async def test_inactive_connection_raises_not_used(status):
    # A non-active connection must be treated as no connection (security
    # decision) — never fetched. The handler raises if any request is made.
    store = InMemoryCredentialStore()
    store.save(Connection("cx", "shopify", "shop-x", "tok-x", ["read_orders"], status))
    svc = MarketingService(store=store, http=FakeHttp(_raise_if_hit), now_iso=NOW_ISO)
    q = QuerySpec(source="shopify", metrics=["total_sales"], start="2026-05-26", end="2026-06-02")
    with pytest.raises(NoConnectionError):
        await svc.run_query("cx", q)
