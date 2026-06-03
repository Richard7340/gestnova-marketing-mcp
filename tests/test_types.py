from datetime import datetime
from gestnova_marketing.types import DataResult, QuerySpec, DateRange


def test_dataresult_ok_carries_metadata():
    r = DataResult(
        source="shopify",
        account_id="shop-123",
        date_range=DateRange(start="2026-05-26", end="2026-06-02"),
        fetched_at="2026-06-03T18:00:00Z",
        status="ok",
        metrics={"total_sales": 1234.5, "orders": 12},
    )
    d = r.to_dict()
    assert d["source"] == "shopify"
    assert d["account_id"] == "shop-123"
    assert d["date_range"] == {"start": "2026-05-26", "end": "2026-06-02"}
    assert d["status"] == "ok"
    assert d["metrics"]["orders"] == 12
    assert d["error"] is None


def test_dataresult_no_data_has_no_metrics_but_reason():
    r = DataResult(
        source="ga4",
        account_id="ga-9",
        date_range=DateRange(start="2026-05-26", end="2026-06-02"),
        fetched_at="2026-06-03T18:00:00Z",
        status="no_data",
        error="GA4 returned 0 rows for the range",
    )
    d = r.to_dict()
    assert d["status"] == "no_data"
    assert d["metrics"] == {}
    assert "0 rows" in d["error"]


def test_queryspec_defaults():
    q = QuerySpec(source="shopify", metrics=["total_sales"],
                  start="2026-05-26", end="2026-06-02")
    assert q.dimensions == []
    assert q.filters == {}
    assert q.source == "shopify"
