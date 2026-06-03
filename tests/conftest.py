"""Shared fixtures: a fake HTTP client backed by httpx.MockTransport, an in-memory
credential store, and helpers to stamp a deterministic fetched_at."""
import json
import httpx
import pytest

from gestnova_marketing.credentials.store import Connection, InMemoryCredentialStore

NOW_ISO = "2026-06-03T18:00:00Z"


class FakeHttp:
    """Routes requests to a handler(request) -> httpx.Response via MockTransport."""
    def __init__(self, handler):
        self._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def request(self, method, url, *, headers=None, params=None, json=None):
        return await self._client.request(method, url, headers=headers, params=params, json=json)


def json_response(payload, status=200):
    return httpx.Response(status, content=json.dumps(payload), headers={"content-type": "application/json"})


@pytest.fixture
def now_iso():
    return NOW_ISO


@pytest.fixture
def store():
    s = InMemoryCredentialStore()
    s.save(Connection("c1", "shopify", "shop-1", "tok-shopify", ["read_orders"], "active"))
    s.save(Connection("c1", "ga4", "properties/111", "tok-ga4", ["analytics.readonly"], "active"))
    s.save(Connection("c1", "google_ads", "123-456-7890", "tok-ads", ["adwords"], "active"))
    s.save(Connection("c2", "shopify", "shop-2", "tok-other", ["read_orders"], "active"))
    return s
