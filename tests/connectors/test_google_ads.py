import pytest
from tests.conftest import FakeHttp, json_response, NOW_ISO
from gestnova_marketing.connectors import get_connector
import gestnova_marketing.connectors.google_ads  # noqa: F401
from gestnova_marketing.credentials.store import Connection
from gestnova_marketing.types import QuerySpec


def _conn():
    return Connection("c1", "google_ads", "123-456-7890", "tok-ads", ["adwords"], "active")


@pytest.mark.asyncio
async def test_ads_performance_aggregates(monkeypatch):
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "dev-tok")
    monkeypatch.setenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "999-999-9999")

    def handler(request):
        assert "customers/1234567890/googleAds:searchStream" in str(request.url)
        assert request.headers["developer-token"] == "dev-tok"
        assert request.headers["Authorization"] == "Bearer tok-ads"
        return json_response([
            {"results": [
                {"metrics": {"costMicros": "5000000", "clicks": "10", "impressions": "1000"}},
                {"metrics": {"costMicros": "3000000", "clicks": "5", "impressions": "400"}},
            ]}
        ])

    conn = get_connector("google_ads", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="google_ads", metrics=["cost", "clicks", "impressions"],
                  start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)

    assert res.status == "ok"
    assert res.metrics["cost"] == 8.0           # 8,000,000 micros -> 8.0
    assert res.metrics["clicks"] == 15
    assert res.metrics["impressions"] == 1400


@pytest.mark.asyncio
async def test_no_results_returns_no_data(monkeypatch):
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "dev-tok")
    monkeypatch.setenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "999-999-9999")

    def handler(request):
        return json_response([{"results": []}])

    conn = get_connector("google_ads", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="google_ads", metrics=["cost"], start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)
    assert res.status == "no_data"


@pytest.mark.asyncio
async def test_missing_developer_token_is_error(monkeypatch):
    monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN", raising=False)

    def handler(request):  # should not be called
        raise AssertionError("must not hit network without dev token")

    conn = get_connector("google_ads", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="google_ads", metrics=["cost"], start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)
    assert res.status == "error"
    assert "developer token" in res.error.lower()


@pytest.mark.asyncio
async def test_non_json_body_is_error(monkeypatch):
    import httpx
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "dev-tok")

    def handler(request):
        return httpx.Response(200, content=b"<html>not json</html>",
                              headers={"content-type": "text/html"})

    conn = get_connector("google_ads", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="google_ads", metrics=["cost"], start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)
    assert res.status == "error"
    assert res.source == "google_ads"
    assert "non-json" in res.error.lower()


@pytest.mark.asyncio
async def test_malformed_metric_does_not_crash(monkeypatch):
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "dev-tok")

    def handler(request):
        return json_response([
            {"results": [
                {"metrics": {"costMicros": "5000000", "clicks": "10", "impressions": "1000"}},
                {"metrics": {"costMicros": "not-a-number", "clicks": None, "impressions": "abc"}},
            ]}
        ])

    conn = get_connector("google_ads", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="google_ads", metrics=["cost", "clicks", "impressions"],
                  start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)
    assert res.status == "ok"
    # malformed row coerces to 0; only the well-formed row counts
    assert res.metrics["cost"] == 5.0
    assert res.metrics["clicks"] == 10
    assert res.metrics["impressions"] == 1000
