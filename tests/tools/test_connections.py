import pytest
from tests.conftest import FakeHttp, json_response, NOW_ISO
from gestnova_marketing.tools.connections import (
    ConnectAccountTool, CompleteConnectionTool, ListConnectionsTool,
)
from gestnova_marketing.credentials.store import InMemoryCredentialStore


@pytest.mark.asyncio
async def test_connect_account_returns_auth_url():
    store = InMemoryCredentialStore()
    tool = ConnectAccountTool(store=store, http=FakeHttp(lambda r: json_response({})), now_iso=NOW_ISO)
    res = await tool.execute({"company_id": "c1", "source": "ga4",
                              "redirect_uri": "https://app.gestnova.eu/cb"})
    assert res["status"] == "ok"
    assert res["auth_url"].startswith("https://")
    assert "ga4" == res["source"]


@pytest.mark.asyncio
async def test_complete_connection_exchanges_code_and_stores():
    store = InMemoryCredentialStore()

    def handler(request):
        # token exchange endpoint
        return json_response({"access_token": "fresh-token", "scope": "analytics.readonly"})

    tool = CompleteConnectionTool(store=store, http=FakeHttp(handler), now_iso=NOW_ISO)
    res = await tool.execute({"company_id": "c1", "source": "ga4",
                              "code": "auth-code", "account_id": "properties/111",
                              "redirect_uri": "https://app.gestnova.eu/cb"})
    assert res["status"] == "ok"
    saved = store.get("c1", "ga4")
    assert saved is not None
    assert saved.token == "fresh-token"
    assert saved.account_id == "properties/111"


@pytest.mark.asyncio
async def test_list_connections_scoped_to_company():
    store = InMemoryCredentialStore()
    from gestnova_marketing.credentials.store import Connection
    store.save(Connection("c1", "shopify", "s1", "t1", ["read"], "active"))
    store.save(Connection("c2", "ga4", "g2", "t2", ["read"], "active"))
    tool = ListConnectionsTool(store=store, http=FakeHttp(lambda r: json_response({})), now_iso=NOW_ISO)
    res = await tool.execute({"company_id": "c1"})
    assert [c["source"] for c in res["connections"]] == ["shopify"]
