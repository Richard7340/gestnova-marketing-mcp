import json

import httpx
import pytest
from tests.conftest import FakeHttp, json_response, NOW_ISO
from gestnova_marketing.connectors import get_connector
import gestnova_marketing.connectors.ga4  # noqa: F401
from gestnova_marketing.credentials.store import Connection
from gestnova_marketing.types import QuerySpec


def _conn():
    return Connection("c1", "ga4", "properties/111", "tok-ga4", ["analytics.readonly"], "active")


@pytest.mark.asyncio
async def test_traffic_summary_parses_runreport():
    def handler(request):
        assert "properties/111:runReport" in str(request.url)
        assert request.headers["Authorization"] == "Bearer tok-ga4"
        return json_response({
            "rows": [
                {"dimensionValues": [{"value": "google"}], "metricValues": [{"value": "120"}, {"value": "90"}]},
                {"dimensionValues": [{"value": "direct"}], "metricValues": [{"value": "30"}, {"value": "25"}]},
            ],
            "metricHeaders": [{"name": "sessions"}, {"name": "activeUsers"}],
            "dimensionHeaders": [{"name": "sessionSource"}],
        })

    conn = get_connector("ga4", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="ga4", metrics=["sessions", "activeUsers"],
                  dimensions=["sessionSource"], start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)

    assert res.status == "ok"
    assert res.metrics["sessions"] == 150
    assert res.metrics["activeUsers"] == 115
    assert len(res.rows) == 2
    assert res.rows[0]["sessionSource"] == "google"
    assert res.rows[0]["sessions"] == 120


@pytest.mark.asyncio
async def test_no_rows_returns_no_data():
    def handler(request):
        return json_response({"rows": [], "metricHeaders": [{"name": "sessions"}]})

    conn = get_connector("ga4", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="ga4", metrics=["sessions"], dimensions=[], start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)
    assert res.status == "no_data"


@pytest.mark.asyncio
async def test_error_status_propagates():
    def handler(request):
        return json_response({"error": {"message": "permission denied"}}, status=403)

    conn = get_connector("ga4", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="ga4", metrics=["sessions"], dimensions=[], start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)
    assert res.status == "error"
    assert "403" in res.error


@pytest.mark.asyncio
async def test_non_json_body_returns_error():
    """Golden rule: a 200 with a non-JSON body must return a DataResult error, never crash."""
    def handler(request):
        return httpx.Response(200, content=b"<html>not json</html>",
                              headers={"content-type": "text/html"})

    conn = get_connector("ga4", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="ga4", metrics=["sessions"], dimensions=[], start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)
    assert res.status == "error"
    assert res.account_id == "properties/111"


@pytest.mark.asyncio
async def test_malformed_metric_value_does_not_crash():
    """Golden rule: a row with a malformed metric value must never raise."""
    def handler(request):
        return json_response({
            "rows": [
                {"dimensionValues": [{"value": "google"}],
                 "metricValues": [{"value": "not-a-number"}]},
            ],
            "metricHeaders": [{"name": "sessions"}],
            "dimensionHeaders": [{"name": "sessionSource"}],
        })

    conn = get_connector("ga4", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="ga4", metrics=["sessions"], dimensions=["sessionSource"],
                  start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)
    assert res.status in ("ok", "error")
    if res.status == "ok":
        # malformed value coerced to 0, never fabricated
        assert res.metrics["sessions"] == 0
        assert res.rows[0]["sessions"] == 0


@pytest.mark.asyncio
async def test_float_metric_value_is_preserved():
    """Golden rule: a fractional metric (e.g. bounceRate 0.42) must NOT be
    truncated to 0 — preserve the float in both the row and the totals."""
    def handler(request):
        return json_response({
            "rows": [
                {"dimensionValues": [{"value": "google"}],
                 "metricValues": [{"value": "0.42"}]},
            ],
            "metricHeaders": [{"name": "bounceRate"}],
            "dimensionHeaders": [{"name": "sessionSource"}],
        })

    conn = get_connector("ga4", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="ga4", metrics=["bounceRate"], dimensions=["sessionSource"],
                  start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)
    assert res.status == "ok"
    assert res.rows[0]["bounceRate"] == 0.42
    assert res.metrics["bounceRate"] == 0.42


def _ok_response():
    return json_response({
        "rows": [
            {"dimensionValues": [{"value": "google"}], "metricValues": [{"value": "10"}]},
        ],
        "metricHeaders": [{"name": "sessions"}],
        "dimensionHeaders": [{"name": "sessionSource"}],
    })


@pytest.mark.asyncio
async def test_single_filter_adds_dimension_filter():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return _ok_response()

    conn = get_connector("ga4", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="ga4", metrics=["sessions"], dimensions=["sessionSource"],
                  start="2026-05-26", end="2026-06-02", filters={"city": "Madrid"})
    res = await conn.fetch(_conn(), q)

    assert res.status == "ok"
    body = captured["body"]
    assert body["dimensionFilter"]["filter"]["fieldName"] == "city"
    assert body["dimensionFilter"]["filter"]["stringFilter"]["value"] == "Madrid"
    assert body["dimensionFilter"]["filter"]["stringFilter"]["matchType"] == "EXACT"


@pytest.mark.asyncio
async def test_multiple_filters_use_and_group():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return _ok_response()

    conn = get_connector("ga4", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="ga4", metrics=["sessions"], dimensions=["sessionSource"],
                  start="2026-05-26", end="2026-06-02",
                  filters={"city": "Madrid", "country": "Spain"})
    res = await conn.fetch(_conn(), q)

    assert res.status == "ok"
    body = captured["body"]
    exprs = body["dimensionFilter"]["andGroup"]["expressions"]
    assert len(exprs) == 2
    fields = {e["filter"]["fieldName"] for e in exprs}
    assert fields == {"city", "country"}


@pytest.mark.asyncio
async def test_empty_filters_omits_dimension_filter():
    """No-regression: an empty filters set must leave the body unchanged."""
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return _ok_response()

    conn = get_connector("ga4", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="ga4", metrics=["sessions"], dimensions=["sessionSource"],
                  start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)

    assert res.status == "ok"
    assert "dimensionFilter" not in captured["body"]
