"""Normalized data contract shared by connectors and tools."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Literal

DataStatus = Literal["ok", "no_data", "error"]


@dataclass(frozen=True)
class DateRange:
    start: str  # ISO date "YYYY-MM-DD"
    end: str    # ISO date "YYYY-MM-DD"


@dataclass
class DataResult:
    """Every connector/tool data response. Carries mandatory provenance metadata."""
    source: str            # "shopify" | "ga4" | "google_ads"
    account_id: str
    date_range: DateRange
    fetched_at: str        # ISO-8601 timestamp
    status: DataStatus
    metrics: dict[str, Any] = field(default_factory=dict)
    rows: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "account_id": self.account_id,
            "date_range": {"start": self.date_range.start, "end": self.date_range.end},
            "fetched_at": self.fetched_at,
            "status": self.status,
            "metrics": self.metrics,
            "rows": self.rows,
            "error": self.error,
        }


@dataclass
class QuerySpec:
    """A normalized request a tool builds and a connector fulfills."""
    source: str
    metrics: list[str]
    start: str
    end: str
    dimensions: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
