# gestnova-marketing-mcp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone, well-structured MCP server that lets the Gestnova agent read and analyze a company's marketing data (Shopify sales, GA4 traffic, Google Ads) per-tenant, WITHOUT wiring it into the agent yet.

**Architecture:** Python MCP (stdio) mirroring `gestnova-accounting-mcp`. A `CredentialStore` abstraction holds per-company OAuth tokens (encrypted-file impl for v1, Postgres-backed in production). Thin connectors (injectable HTTP client) call provider APIs live and return a normalized `DataResult` carrying mandatory metadata (`source`, `account_id`, `date_range`, `fetched_at`, `status`). Tools resolve the caller's `company_id`, enforce tenant isolation, build a `QuerySpec`, and delegate to a connector. No data warehouse — history comes from the APIs; the agent's memory holds continuity (wiring later).

**Tech Stack:** Python ≥3.11, `uv`, `mcp`, `httpx` (async, mockable transport), `cryptography` (Fernet token encryption), `pydantic`, `pytest` + `pytest-asyncio`. Hatchling build, `src/gestnova_marketing` layout.

**Model guidance (per Riky):** Use Opus 4.8 for the harder tasks (connectors, OAuth exchange, tenant isolation, credential encryption); Opus 4.7 is fine for scaffolding and the simpler canned tools. Pick per task difficulty.

**Golden rule (system-level):** Zero invention. On API failure or missing data, tools return `status: "no_data" | "error"` with a reason — never fabricated numbers. Every datum carries `source` + date.

---

## File Structure

```
gestnova-marketing-mcp/
├── pyproject.toml                         # uv/hatchling, deps, scripts (Task 1)
├── README.md                              # integration doc (Task 15)
├── Dockerfile                             # parity with accounting-mcp (Task 15)
├── src/gestnova_marketing/
│   ├── __init__.py                        # __version__ (Task 1)
│   ├── server.py                          # in-proc wrapper + stdio entrypoint (Task 1)
│   ├── http_server.py                     # HTTP parity entrypoint (Task 14)
│   ├── types.py                           # DataResult, QuerySpec, DataStatus (Task 2)
│   ├── credentials/
│   │   ├── __init__.py
│   │   ├── store.py                       # Connection + CredentialStore ABC + InMemory (Task 3)
│   │   └── encrypted_file.py              # Fernet-encrypted file store (Task 4)
│   ├── connectors/
│   │   ├── __init__.py                    # registry get_connector() (Task 5)
│   │   ├── _base.py                       # Connector ABC + HttpClient protocol (Task 5)
│   │   ├── shopify.py                     # (Task 6)
│   │   ├── ga4.py                         # (Task 7)
│   │   └── google_ads.py                  # (Task 8)
│   ├── service.py                         # MarketingService: resolve conn + isolation (Task 9)
│   └── tools/
│       ├── __init__.py                    # get_all_tools() registry + PingTool (Task 1)
│       ├── _base.py                       # BaseTool ABC (Task 1)
│       ├── connections.py                 # connect / complete / list (Task 10)
│       └── reports.py                     # sales/traffic/ads/overview/query (Tasks 11-12)
└── tests/
    ├── conftest.py                        # fixtures: fake http, in-memory store, server (Task 5)
    ├── test_smoke_mcp.py                  # ping smoke (Task 1)
    ├── test_types.py                      # (Task 2)
    ├── credentials/test_store.py          # (Task 3)
    ├── credentials/test_encrypted_file.py # (Task 4)
    ├── connectors/test_shopify.py         # (Task 6)
    ├── connectors/test_ga4.py             # (Task 7)
    ├── connectors/test_google_ads.py      # (Task 8)
    ├── test_service_isolation.py          # tenant isolation (Task 9)
    ├── tools/test_connections.py          # (Task 10)
    ├── tools/test_reports.py              # (Tasks 11-12)
    └── tools/test_no_invention.py         # golden-rule propagation (Task 13)
```

---

## Task 1: Repo scaffold + ping smoke test

**Files:**
- Create: `pyproject.toml`, `src/gestnova_marketing/__init__.py`, `src/gestnova_marketing/server.py`, `src/gestnova_marketing/tools/__init__.py`, `src/gestnova_marketing/tools/_base.py`
- Test: `tests/test_smoke_mcp.py`, `tests/__init__.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "gestnova-marketing"
version = "0.1.0"
description = "MCP server for marketing data (Shopify, GA4, Google Ads) — read/analyze per-tenant"
requires-python = ">=3.11"
dependencies = [
    "mcp>=0.9.0",
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "httpx>=0.27.0",
    "cryptography>=42.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.3.0",
    "mypy>=1.8.0",
]

[project.scripts]
gestnova-marketing-mcp = "gestnova_marketing.server:main"
gestnova-marketing-http = "gestnova_marketing.http_server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/gestnova_marketing"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Write `src/gestnova_marketing/__init__.py`**

```python
"""Gestnova marketing MCP — per-tenant marketing data (Shopify, GA4, Google Ads)."""
__version__ = "0.1.0"
```

- [ ] **Step 3: Write `src/gestnova_marketing/tools/_base.py`**

```python
"""Base class shared by all MCP tools."""
from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    name: str
    description: str
    input_schema: dict[str, Any]

    @abstractmethod
    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        ...
```

- [ ] **Step 4: Write `src/gestnova_marketing/tools/__init__.py` with PingTool only**

```python
"""Tool registry."""
from typing import Any
from ._base import BaseTool


class PingTool(BaseTool):
    name = "ping"
    description = "Health check — returns server status and version."
    input_schema = {"type": "object", "properties": {}, "required": []}

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        from gestnova_marketing import __version__
        return {"status": "ok", "version": __version__}


def get_all_tools() -> list[BaseTool]:
    return [
        PingTool(),
    ]
```

- [ ] **Step 5: Write `src/gestnova_marketing/server.py`** (clone of accounting pattern)

```python
"""MCP stdio server entrypoint."""
import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool as McpTool, TextContent

from gestnova_marketing.tools import get_all_tools


class MarketingServer:
    """In-process wrapper so tests can call tools without going through stdio."""

    def __init__(self):
        self._tools = {t.name: t for t in get_all_tools()}

    async def list_tools(self) -> list:
        return list(self._tools.values())

    async def call_tool(self, name: str, args: dict) -> dict:
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")
        return await self._tools[name].execute(args)


def build_server() -> MarketingServer:
    return MarketingServer()


async def _run_stdio():
    server = Server("gestnova-marketing")
    in_proc = build_server()

    @server.list_tools()
    async def list_tools_handler() -> list[McpTool]:
        tools = await in_proc.list_tools()
        return [
            McpTool(name=t.name, description=t.description, inputSchema=t.input_schema)
            for t in tools
        ]

    @server.call_tool()
    async def call_tool_handler(name: str, arguments: dict) -> list[TextContent]:
        result = await in_proc.call_tool(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, default=str))]

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main():
    asyncio.run(_run_stdio())


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Write `tests/__init__.py` (empty) and `tests/test_smoke_mcp.py`**

```python
import pytest
from gestnova_marketing.server import build_server


@pytest.mark.asyncio
async def test_ping_returns_ok():
    server = build_server()
    res = await server.call_tool("ping", {})
    assert res["status"] == "ok"
    assert res["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_unknown_tool_raises():
    server = build_server()
    with pytest.raises(ValueError):
        await server.call_tool("does_not_exist", {})
```

- [ ] **Step 7: Install deps and run the smoke test**

Run: `cd "/Users/rikyizquierdo/Documents/New project/gestnova-marketing-mcp" && uv venv && uv pip install -e ".[dev]" && uv run pytest tests/test_smoke_mcp.py -v`
Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat: scaffold gestnova-marketing-mcp with ping smoke test"
```

---

## Task 2: Normalized result types (`DataResult`, `QuerySpec`)

**Files:**
- Create: `src/gestnova_marketing/types.py`
- Test: `tests/test_types.py`

- [ ] **Step 1: Write the failing test `tests/test_types.py`**

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_types.py -v`
Expected: FAIL with `ModuleNotFoundError: gestnova_marketing.types`.

- [ ] **Step 3: Write `src/gestnova_marketing/types.py`**

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_types.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: normalized DataResult + QuerySpec contract"
```

---

## Task 3: `CredentialStore` interface + in-memory implementation

**Files:**
- Create: `src/gestnova_marketing/credentials/__init__.py`, `src/gestnova_marketing/credentials/store.py`
- Test: `tests/credentials/__init__.py`, `tests/credentials/test_store.py`

- [ ] **Step 1: Write the failing test `tests/credentials/test_store.py`**

```python
import pytest
from gestnova_marketing.credentials.store import Connection, InMemoryCredentialStore


def test_save_and_get_roundtrips():
    store = InMemoryCredentialStore()
    conn = Connection(company_id="c1", source="shopify", account_id="shop-1",
                      token="tok-abc", scopes=["read_orders"], status="active")
    store.save(conn)
    got = store.get("c1", "shopify")
    assert got is not None
    assert got.token == "tok-abc"
    assert got.account_id == "shop-1"


def test_get_returns_none_when_absent():
    store = InMemoryCredentialStore()
    assert store.get("c1", "ga4") is None


def test_list_for_company_only_returns_that_company():
    store = InMemoryCredentialStore()
    store.save(Connection("c1", "shopify", "s1", "t1", ["read"], "active"))
    store.save(Connection("c1", "ga4", "g1", "t2", ["read"], "active"))
    store.save(Connection("c2", "shopify", "s2", "t3", ["read"], "active"))
    conns = store.list_for_company("c1")
    assert {c.source for c in conns} == {"shopify", "ga4"}
    assert all(c.company_id == "c1" for c in conns)


def test_save_overwrites_same_company_source():
    store = InMemoryCredentialStore()
    store.save(Connection("c1", "shopify", "s1", "old", ["read"], "active"))
    store.save(Connection("c1", "shopify", "s1", "new", ["read"], "active"))
    assert store.get("c1", "shopify").token == "new"
    assert len(store.list_for_company("c1")) == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/credentials/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/gestnova_marketing/credentials/__init__.py` (empty) and `store.py`**

```python
"""Credential storage abstraction. v1 ships InMemory + EncryptedFile impls.
In production this interface is backed by Gestnova's existing Postgres."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Connection:
    company_id: str
    source: str          # "shopify" | "ga4" | "google_ads"
    account_id: str
    token: str           # decrypted access token (in-memory only)
    scopes: list[str]
    status: str          # "active" | "expired" | "revoked"


class CredentialStore(ABC):
    @abstractmethod
    def save(self, conn: Connection) -> None: ...

    @abstractmethod
    def get(self, company_id: str, source: str) -> Connection | None: ...

    @abstractmethod
    def list_for_company(self, company_id: str) -> list[Connection]: ...


class InMemoryCredentialStore(CredentialStore):
    """Test/dev store. Keyed by (company_id, source)."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str], Connection] = {}

    def save(self, conn: Connection) -> None:
        self._data[(conn.company_id, conn.source)] = conn

    def get(self, company_id: str, source: str) -> Connection | None:
        return self._data.get((company_id, source))

    def list_for_company(self, company_id: str) -> list[Connection]:
        return [c for (cid, _), c in self._data.items() if cid == company_id]
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/credentials/test_store.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: CredentialStore interface + in-memory impl"
```

---

## Task 4: Encrypted-file `CredentialStore`

**Files:**
- Create: `src/gestnova_marketing/credentials/encrypted_file.py`
- Test: `tests/credentials/test_encrypted_file.py`

- [ ] **Step 1: Write the failing test `tests/credentials/test_encrypted_file.py`**

```python
from pathlib import Path
from cryptography.fernet import Fernet
from gestnova_marketing.credentials.store import Connection
from gestnova_marketing.credentials.encrypted_file import EncryptedFileCredentialStore


def test_token_is_encrypted_at_rest(tmp_path: Path):
    key = Fernet.generate_key().decode()
    path = tmp_path / "creds.json"
    store = EncryptedFileCredentialStore(path=path, key=key)
    store.save(Connection("c1", "shopify", "s1", "super-secret-token", ["read"], "active"))

    raw = path.read_text(encoding="utf-8")
    assert "super-secret-token" not in raw  # token must not be stored in cleartext


def test_roundtrip_decrypts(tmp_path: Path):
    key = Fernet.generate_key().decode()
    path = tmp_path / "creds.json"
    store = EncryptedFileCredentialStore(path=path, key=key)
    store.save(Connection("c1", "ga4", "g1", "tok-123", ["read"], "active"))

    # New instance, same key + file: must decrypt the token back.
    store2 = EncryptedFileCredentialStore(path=path, key=key)
    got = store2.get("c1", "ga4")
    assert got is not None
    assert got.token == "tok-123"


def test_list_for_company_isolated(tmp_path: Path):
    key = Fernet.generate_key().decode()
    store = EncryptedFileCredentialStore(path=tmp_path / "c.json", key=key)
    store.save(Connection("c1", "shopify", "s1", "t1", ["read"], "active"))
    store.save(Connection("c2", "shopify", "s2", "t2", ["read"], "active"))
    assert [c.company_id for c in store.list_for_company("c1")] == ["c1"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/credentials/test_encrypted_file.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/gestnova_marketing/credentials/encrypted_file.py`**

```python
"""File-backed CredentialStore with Fernet-encrypted tokens. v1/dev only.
Production backs the same CredentialStore interface with Gestnova's Postgres."""
from __future__ import annotations
import json
from pathlib import Path

from cryptography.fernet import Fernet

from .store import Connection, CredentialStore


class EncryptedFileCredentialStore(CredentialStore):
    def __init__(self, path: Path, key: str) -> None:
        self._path = Path(path)
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def _load(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _dump(self, data: dict[str, dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def _key(company_id: str, source: str) -> str:
        return f"{company_id}::{source}"

    def save(self, conn: Connection) -> None:
        data = self._load()
        data[self._key(conn.company_id, conn.source)] = {
            "company_id": conn.company_id,
            "source": conn.source,
            "account_id": conn.account_id,
            "token_enc": self._fernet.encrypt(conn.token.encode()).decode(),
            "scopes": conn.scopes,
            "status": conn.status,
        }
        self._dump(data)

    def _to_conn(self, rec: dict) -> Connection:
        return Connection(
            company_id=rec["company_id"],
            source=rec["source"],
            account_id=rec["account_id"],
            token=self._fernet.decrypt(rec["token_enc"].encode()).decode(),
            scopes=rec["scopes"],
            status=rec["status"],
        )

    def get(self, company_id: str, source: str) -> Connection | None:
        rec = self._load().get(self._key(company_id, source))
        return self._to_conn(rec) if rec else None

    def list_for_company(self, company_id: str) -> list[Connection]:
        return [
            self._to_conn(rec)
            for rec in self._load().values()
            if rec["company_id"] == company_id
        ]
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/credentials/test_encrypted_file.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: Fernet-encrypted file CredentialStore"
```

---

## Task 5: Connector base + HTTP client protocol + shared test fixtures

**Files:**
- Create: `src/gestnova_marketing/connectors/__init__.py`, `src/gestnova_marketing/connectors/_base.py`
- Create: `tests/conftest.py`, `tests/connectors/__init__.py`

- [ ] **Step 1: Write `src/gestnova_marketing/connectors/_base.py`**

```python
"""Connector base + injectable async HTTP client protocol."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Protocol

import httpx

from gestnova_marketing.credentials.store import Connection
from gestnova_marketing.types import DataResult, QuerySpec


class HttpClient(Protocol):
    async def request(self, method: str, url: str, *,
                      headers: dict[str, str] | None = None,
                      params: dict[str, Any] | None = None,
                      json: dict[str, Any] | None = None) -> httpx.Response: ...


class Connector(ABC):
    source: str

    def __init__(self, http: HttpClient, *, now_iso: str) -> None:
        """now_iso is injected (the fetched_at stamp) so results are deterministic in tests."""
        self._http = http
        self._now = now_iso

    @abstractmethod
    async def fetch(self, conn: Connection, query: QuerySpec) -> DataResult: ...
```

- [ ] **Step 2: Write `src/gestnova_marketing/connectors/__init__.py` (registry stub — connectors added in later tasks)**

```python
"""Connector registry."""
from __future__ import annotations
from ._base import Connector, HttpClient

_REGISTRY: dict[str, type[Connector]] = {}


def register(source: str):
    def deco(cls: type[Connector]) -> type[Connector]:
        cls.source = source
        _REGISTRY[source] = cls
        return cls
    return deco


def get_connector(source: str, http: HttpClient, *, now_iso: str) -> Connector:
    if source not in _REGISTRY:
        raise ValueError(f"Unknown source: {source}")
    return _REGISTRY[source](http, now_iso=now_iso)


def supported_sources() -> list[str]:
    return sorted(_REGISTRY)
```

- [ ] **Step 3: Write `tests/connectors/__init__.py` (empty) and `tests/conftest.py`**

```python
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
```

- [ ] **Step 4: Verify imports resolve (no test yet, just import-check)**

Run: `uv run python -c "import gestnova_marketing.connectors as c; print(c.supported_sources())"`
Expected: prints `[]` (no connectors registered yet), no import error.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: connector base, HTTP protocol, registry, test fixtures"
```

---

## Task 6: Shopify connector

**Files:**
- Create: `src/gestnova_marketing/connectors/shopify.py`
- Test: `tests/connectors/test_shopify.py`

- [ ] **Step 1: Write the failing test `tests/connectors/test_shopify.py`**

```python
import pytest
from tests.conftest import FakeHttp, json_response, NOW_ISO
from gestnova_marketing.connectors import get_connector
import gestnova_marketing.connectors.shopify  # noqa: F401  (registers connector)
from gestnova_marketing.credentials.store import Connection
from gestnova_marketing.types import QuerySpec


def _conn():
    return Connection("c1", "shopify", "shop-1", "tok-shopify", ["read_orders"], "active")


@pytest.mark.asyncio
async def test_sales_summary_aggregates_orders():
    def handler(request):
        assert "shop-1.myshopify.com" in str(request.url)
        assert request.headers["X-Shopify-Access-Token"] == "tok-shopify"
        return json_response({"orders": [
            {"total_price": "100.50", "id": 1},
            {"total_price": "49.50", "id": 2},
        ]})

    conn = get_connector("shopify", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="shopify", metrics=["total_sales", "orders"],
                  start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)

    assert res.status == "ok"
    assert res.source == "shopify"
    assert res.account_id == "shop-1"
    assert res.fetched_at == NOW_ISO
    assert res.metrics["orders"] == 2
    assert res.metrics["total_sales"] == 150.0


@pytest.mark.asyncio
async def test_no_orders_returns_no_data():
    def handler(request):
        return json_response({"orders": []})

    conn = get_connector("shopify", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="shopify", metrics=["total_sales"], start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)
    assert res.status == "no_data"
    assert res.metrics == {}
    assert res.error is not None


@pytest.mark.asyncio
async def test_api_error_returns_error_status():
    def handler(request):
        return json_response({"errors": "Not authorized"}, status=401)

    conn = get_connector("shopify", FakeHttp(handler), now_iso=NOW_ISO)
    q = QuerySpec(source="shopify", metrics=["total_sales"], start="2026-05-26", end="2026-06-02")
    res = await conn.fetch(_conn(), q)
    assert res.status == "error"
    assert "401" in res.error
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/connectors/test_shopify.py -v`
Expected: FAIL (`shopify` not in registry / module attribute errors).

- [ ] **Step 3: Write `src/gestnova_marketing/connectors/shopify.py`**

```python
"""Shopify connector — sales/orders for a date range.
Docs: Admin REST API GET /admin/api/<ver>/orders.json"""
from __future__ import annotations

from gestnova_marketing.connectors import register
from gestnova_marketing.connectors._base import Connector
from gestnova_marketing.credentials.store import Connection
from gestnova_marketing.types import DataResult, DateRange, QuerySpec

API_VERSION = "2024-04"


@register("shopify")
class ShopifyConnector(Connector):
    async def fetch(self, conn: Connection, query: QuerySpec) -> DataResult:
        dr = DateRange(start=query.start, end=query.end)
        base = {"source": "shopify", "account_id": conn.account_id,
                "date_range": dr, "fetched_at": self._now}
        url = f"https://{conn.account_id}.myshopify.com/admin/api/{API_VERSION}/orders.json"
        params = {
            "status": "any",
            "created_at_min": f"{query.start}T00:00:00Z",
            "created_at_max": f"{query.end}T23:59:59Z",
            "limit": 250,
        }
        headers = {"X-Shopify-Access-Token": conn.token}
        try:
            resp = await self._http.request("GET", url, headers=headers, params=params)
        except Exception as exc:  # network failure — never fabricate
            return DataResult(**base, status="error", error=f"request failed: {exc}")

        if resp.status_code != 200:
            return DataResult(**base, status="error",
                              error=f"shopify HTTP {resp.status_code}: {resp.text[:200]}")

        orders = resp.json().get("orders", [])
        if not orders:
            return DataResult(**base, status="no_data",
                              error="shopify returned 0 orders for the range")

        total = round(sum(float(o.get("total_price", 0)) for o in orders), 2)
        return DataResult(**base, status="ok",
                          metrics={"orders": len(orders), "total_sales": total},
                          rows=[{"id": o.get("id"), "total_price": o.get("total_price")} for o in orders])
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/connectors/test_shopify.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: Shopify connector (sales/orders)"
```

---

## Task 7: GA4 connector

**Files:**
- Create: `src/gestnova_marketing/connectors/ga4.py`
- Test: `tests/connectors/test_ga4.py`

- [ ] **Step 1: Write the failing test `tests/connectors/test_ga4.py`**

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/connectors/test_ga4.py -v`
Expected: FAIL.

- [ ] **Step 3: Write `src/gestnova_marketing/connectors/ga4.py`**

```python
"""GA4 connector — Data API v1 runReport. account_id is the GA4 property
resource name, e.g. "properties/111". Token is an OAuth access token."""
from __future__ import annotations

from gestnova_marketing.connectors import register
from gestnova_marketing.connectors._base import Connector
from gestnova_marketing.credentials.store import Connection
from gestnova_marketing.types import DataResult, DateRange, QuerySpec


@register("ga4")
class GA4Connector(Connector):
    async def fetch(self, conn: Connection, query: QuerySpec) -> DataResult:
        dr = DateRange(start=query.start, end=query.end)
        base = {"source": "ga4", "account_id": conn.account_id,
                "date_range": dr, "fetched_at": self._now}
        url = f"https://analyticsdata.googleapis.com/v1beta/{conn.account_id}:runReport"
        body = {
            "dateRanges": [{"startDate": query.start, "endDate": query.end}],
            "metrics": [{"name": m} for m in query.metrics],
            "dimensions": [{"name": d} for d in query.dimensions],
        }
        headers = {"Authorization": f"Bearer {conn.token}"}
        try:
            resp = await self._http.request("POST", url, headers=headers, json=body)
        except Exception as exc:
            return DataResult(**base, status="error", error=f"request failed: {exc}")

        if resp.status_code != 200:
            return DataResult(**base, status="error",
                              error=f"ga4 HTTP {resp.status_code}: {resp.text[:200]}")

        payload = resp.json()
        rows = payload.get("rows", [])
        if not rows:
            return DataResult(**base, status="no_data",
                              error="ga4 returned 0 rows for the range")

        metric_names = [h["name"] for h in payload.get("metricHeaders", [])]
        dim_names = [h["name"] for h in payload.get("dimensionHeaders", [])]

        totals = {m: 0 for m in metric_names}
        out_rows: list[dict] = []
        for r in rows:
            row: dict = {}
            for i, dv in enumerate(r.get("dimensionValues", [])):
                row[dim_names[i]] = dv["value"]
            for i, mv in enumerate(r.get("metricValues", [])):
                val = int(float(mv["value"]))
                row[metric_names[i]] = val
                totals[metric_names[i]] += val
            out_rows.append(row)

        return DataResult(**base, status="ok", metrics=totals, rows=out_rows)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/connectors/test_ga4.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: GA4 connector (traffic via runReport)"
```

---

## Task 8: Google Ads connector

**Files:**
- Create: `src/gestnova_marketing/connectors/google_ads.py`
- Test: `tests/connectors/test_google_ads.py`

> NOTE (sequencing, from spec §8): this connector needs a Google Ads **developer
> token with Basic/Standard access** plus the manager (MCC) customer id, supplied
> via env at runtime. The test uses a fake transport; live verification is a
> separate manual step requiring real credentials.

- [ ] **Step 1: Write the failing test `tests/connectors/test_google_ads.py`**

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/connectors/test_google_ads.py -v`
Expected: FAIL.

- [ ] **Step 3: Write `src/gestnova_marketing/connectors/google_ads.py`**

```python
"""Google Ads connector — searchStream GAQL over the REST API.
account_id is the client customer id (e.g. "123-456-7890"). Requires a
developer token (Gestnova MCC) + login-customer-id from env."""
from __future__ import annotations
import os

from gestnova_marketing.connectors import register
from gestnova_marketing.connectors._base import Connector
from gestnova_marketing.credentials.store import Connection
from gestnova_marketing.types import DataResult, DateRange, QuerySpec

API_VERSION = "v17"

# GAQL field per normalized metric name.
_METRIC_FIELD = {
    "cost": "metrics.cost_micros",
    "clicks": "metrics.clicks",
    "impressions": "metrics.impressions",
}


@register("google_ads")
class GoogleAdsConnector(Connector):
    async def fetch(self, conn: Connection, query: QuerySpec) -> DataResult:
        dr = DateRange(start=query.start, end=query.end)
        base = {"source": "google_ads", "account_id": conn.account_id,
                "date_range": dr, "fetched_at": self._now}

        dev_token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
        if not dev_token:
            return DataResult(**base, status="error",
                              error="missing Google Ads developer token (GOOGLE_ADS_DEVELOPER_TOKEN)")
        login_cid = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")
        customer_id = conn.account_id.replace("-", "")

        fields = ", ".join(_METRIC_FIELD[m] for m in query.metrics if m in _METRIC_FIELD)
        gaql = (f"SELECT {fields} FROM customer "
                f"WHERE segments.date BETWEEN '{query.start}' AND '{query.end}'")
        url = (f"https://googleads.googleapis.com/{API_VERSION}/"
               f"customers/{customer_id}/googleAds:searchStream")
        headers = {
            "Authorization": f"Bearer {conn.token}",
            "developer-token": dev_token,
        }
        if login_cid:
            headers["login-customer-id"] = login_cid

        try:
            resp = await self._http.request("POST", url, headers=headers, json={"query": gaql})
        except Exception as exc:
            return DataResult(**base, status="error", error=f"request failed: {exc}")

        if resp.status_code != 200:
            return DataResult(**base, status="error",
                              error=f"google_ads HTTP {resp.status_code}: {resp.text[:200]}")

        # searchStream returns a list of batches, each with "results".
        batches = resp.json()
        results = [r for b in batches for r in b.get("results", [])]
        if not results:
            return DataResult(**base, status="no_data",
                              error="google_ads returned 0 rows for the range")

        totals = {m: 0 for m in query.metrics}
        for r in results:
            m = r.get("metrics", {})
            if "cost" in totals:
                totals["cost"] += int(m.get("costMicros", 0))
            if "clicks" in totals:
                totals["clicks"] += int(m.get("clicks", 0))
            if "impressions" in totals:
                totals["impressions"] += int(m.get("impressions", 0))
        if "cost" in totals:
            totals["cost"] = round(totals["cost"] / 1_000_000, 2)  # micros -> currency

        return DataResult(**base, status="ok", metrics=totals)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/connectors/test_google_ads.py -v`
Expected: 3 passed.

- [ ] **Step 5: Make the registry self-populate at runtime**

The connectors register via `@register` on import, but nothing imports them at
runtime (only tests do, explicitly). Append these imports to the BOTTOM of
`src/gestnova_marketing/connectors/__init__.py` (after `register`/`get_connector`
are defined, so there's no circular-import problem) so the registry fills itself:

```python

# Import connector modules so their @register decorators run on package import.
from . import shopify as _shopify  # noqa: E402,F401
from . import ga4 as _ga4          # noqa: E402,F401
from . import google_ads as _google_ads  # noqa: E402,F401
```

- [ ] **Step 6: Verify the registry is populated without explicit imports**

Run: `uv run python -c "import gestnova_marketing.connectors as c; print(c.supported_sources())"`
Expected: prints `['ga4', 'google_ads', 'shopify']` (no manual submodule import needed).

- [ ] **Step 7: Run the full connector suite**

Run: `uv run pytest tests/connectors -v`
Expected: all connector tests pass.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat: Google Ads connector + self-populating connector registry"
```

---

## Task 9: `MarketingService` — resolve connection + tenant isolation

**Files:**
- Create: `src/gestnova_marketing/service.py`
- Test: `tests/test_service_isolation.py`

- [ ] **Step 1: Write the failing test `tests/test_service_isolation.py`**

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_service_isolation.py -v`
Expected: FAIL (`gestnova_marketing.service` missing).

- [ ] **Step 3: Write `src/gestnova_marketing/service.py`**

```python
"""MarketingService — the only path tools use to reach data.
Enforces tenant isolation: every operation is scoped to one company_id and can
ONLY use that company's stored credentials."""
from __future__ import annotations

from gestnova_marketing.connectors import get_connector, HttpClient
from gestnova_marketing.credentials.store import CredentialStore
from gestnova_marketing.types import DataResult, QuerySpec


class NoConnectionError(Exception):
    """Raised when the company has no active connection for the requested source."""


class MarketingService:
    def __init__(self, store: CredentialStore, http: HttpClient, *, now_iso: str) -> None:
        self._store = store
        self._http = http
        self._now = now_iso

    async def run_query(self, company_id: str, query: QuerySpec) -> DataResult:
        conn = self._store.get(company_id, query.source)
        if conn is None or conn.status != "active":
            raise NoConnectionError(
                f"company {company_id} has no active {query.source} connection")
        connector = get_connector(query.source, self._http, now_iso=self._now)
        return await connector.fetch(conn, query)

    def list_connections(self, company_id: str) -> list[dict]:
        return [
            {"source": c.source, "account_id": c.account_id, "status": c.status,
             "scopes": c.scopes}
            for c in self._store.list_for_company(company_id)
        ]
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_service_isolation.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: MarketingService with enforced tenant isolation"
```

---

## Task 10: Connection tools (`marketingConnectAccount`, `marketingCompleteConnection`, `marketingListConnections`)

**Files:**
- Create: `src/gestnova_marketing/tools/connections.py`
- Modify: `src/gestnova_marketing/tools/__init__.py` (register new tools + shared service factory)
- Test: `tests/tools/__init__.py`, `tests/tools/test_connections.py`

> OAuth model (spec §4): `marketingConnectAccount` returns the provider authorization
> URL the platform/user must visit. `marketingCompleteConnection` exchanges the
> returned `code` for an access token via the provider token endpoint and stores it.
> The redirect/callback hosting belongs to the platform (wiring later).

- [ ] **Step 1: Write the failing test `tests/tools/test_connections.py`**

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/tools/test_connections.py -v`
Expected: FAIL.

- [ ] **Step 3: Write `src/gestnova_marketing/tools/connections.py`**

```python
"""Connection lifecycle tools: build auth URL, exchange code, list connections."""
from __future__ import annotations
from typing import Any

from ._base import BaseTool
from gestnova_marketing.connectors import HttpClient
from gestnova_marketing.credentials.store import Connection, CredentialStore
from gestnova_marketing.service import MarketingService

# Minimal provider OAuth metadata (v1 read scopes).
_PROVIDER = {
    "shopify": {
        "auth": "https://{shop}.myshopify.com/admin/oauth/authorize",
        "token": "https://{shop}.myshopify.com/admin/oauth/access_token",
        "scope": "read_orders,read_products",
    },
    "ga4": {
        "auth": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scope": "https://www.googleapis.com/auth/analytics.readonly",
    },
    "google_ads": {
        "auth": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scope": "https://www.googleapis.com/auth/adwords",
    },
}

_COMPANY_PROP = {"company_id": {"type": "string"}}


class ConnectAccountTool(BaseTool):
    name = "marketingConnectAccount"
    description = "Start OAuth for a source (shopify|ga4|google_ads). Returns the authorization URL to visit."
    input_schema = {
        "type": "object",
        "properties": {
            **_COMPANY_PROP,
            "source": {"type": "string", "enum": ["shopify", "ga4", "google_ads"]},
            "redirect_uri": {"type": "string"},
            "shop": {"type": "string", "description": "Shopify shop subdomain (shopify only)"},
        },
        "required": ["company_id", "source", "redirect_uri"],
    }

    def __init__(self, store: CredentialStore, http: HttpClient, *, now_iso: str) -> None:
        self._store, self._http, self._now = store, http, now_iso

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        source = args["source"]
        meta = _PROVIDER[source]
        auth = meta["auth"].format(shop=args.get("shop", ""))
        # Real client_id comes from env at runtime; placeholder marker kept explicit.
        import os
        client_id = os.environ.get(f"{source.upper()}_CLIENT_ID", "")
        url = (f"{auth}?client_id={client_id}&redirect_uri={args['redirect_uri']}"
               f"&response_type=code&scope={meta['scope']}&state={args['company_id']}")
        return {"status": "ok", "source": source, "auth_url": url}


class CompleteConnectionTool(BaseTool):
    name = "marketingCompleteConnection"
    description = "Exchange an OAuth authorization code for an access token and store it for the company."
    input_schema = {
        "type": "object",
        "properties": {
            **_COMPANY_PROP,
            "source": {"type": "string", "enum": ["shopify", "ga4", "google_ads"]},
            "code": {"type": "string"},
            "account_id": {"type": "string"},
            "redirect_uri": {"type": "string"},
            "shop": {"type": "string"},
        },
        "required": ["company_id", "source", "code", "account_id", "redirect_uri"],
    }

    def __init__(self, store: CredentialStore, http: HttpClient, *, now_iso: str) -> None:
        self._store, self._http, self._now = store, http, now_iso

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        import os
        source = args["source"]
        meta = _PROVIDER[source]
        token_url = meta["token"].format(shop=args.get("shop", ""))
        payload = {
            "code": args["code"],
            "client_id": os.environ.get(f"{source.upper()}_CLIENT_ID", ""),
            "client_secret": os.environ.get(f"{source.upper()}_CLIENT_SECRET", ""),
            "redirect_uri": args["redirect_uri"],
            "grant_type": "authorization_code",
        }
        try:
            resp = await self._http.request("POST", token_url, json=payload)
        except Exception as exc:
            return {"status": "error", "error": f"token exchange failed: {exc}"}
        if resp.status_code != 200:
            return {"status": "error",
                    "error": f"token exchange HTTP {resp.status_code}: {resp.text[:200]}"}
        token = resp.json().get("access_token")
        if not token:
            return {"status": "error", "error": "no access_token in provider response"}
        self._store.save(Connection(
            company_id=args["company_id"], source=source, account_id=args["account_id"],
            token=token, scopes=meta["scope"].split(","), status="active",
        ))
        return {"status": "ok", "source": source, "account_id": args["account_id"]}


class ListConnectionsTool(BaseTool):
    name = "marketingListConnections"
    description = "List the marketing connections for a company and their status."
    input_schema = {"type": "object", "properties": _COMPANY_PROP, "required": ["company_id"]}

    def __init__(self, store: CredentialStore, http: HttpClient, *, now_iso: str) -> None:
        self._svc = MarketingService(store=store, http=http, now_iso=now_iso)

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "connections": self._svc.list_connections(args["company_id"])}
```

- [ ] **Step 4: Update `tools/__init__.py` to wire a shared store/http and register tools**

Replace the file with:

```python
"""Tool registry."""
from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from ._base import BaseTool
from gestnova_marketing.credentials.store import CredentialStore, InMemoryCredentialStore
from gestnova_marketing.credentials.encrypted_file import EncryptedFileCredentialStore


class _DefaultHttp:
    """Real async HTTP client used at runtime (tools accept any HttpClient in tests)."""
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)

    async def request(self, method, url, *, headers=None, params=None, json=None):
        return await self._client.request(method, url, headers=headers, params=params, json=json)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_store() -> CredentialStore:
    key = os.environ.get("MARKETING_CRED_KEY")
    path = os.environ.get("MARKETING_CRED_PATH")
    if key and path:
        return EncryptedFileCredentialStore(path=Path(path), key=key)
    return InMemoryCredentialStore()


class PingTool(BaseTool):
    name = "ping"
    description = "Health check — returns server status and version."
    input_schema = {"type": "object", "properties": {}, "required": []}

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        from gestnova_marketing import __version__
        return {"status": "ok", "version": __version__}


def get_all_tools() -> list[BaseTool]:
    from .connections import ConnectAccountTool, CompleteConnectionTool, ListConnectionsTool

    store = _build_store()
    http = _DefaultHttp()
    now = _now_iso()
    return [
        PingTool(),
        ConnectAccountTool(store=store, http=http, now_iso=now),
        CompleteConnectionTool(store=store, http=http, now_iso=now),
        ListConnectionsTool(store=store, http=http, now_iso=now),
    ]
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/tools/test_connections.py tests/test_smoke_mcp.py -v`
Expected: all passed (smoke still green with expanded registry).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: connection tools (connect/complete/list) + shared store wiring"
```

---

## Task 11: Canned report tools (`marketingSales`, `marketingTraffic`, `marketingAds`)

**Files:**
- Create: `src/gestnova_marketing/tools/reports.py`
- Modify: `src/gestnova_marketing/tools/__init__.py` (register the three tools)
- Test: `tests/tools/test_reports.py`

- [ ] **Step 1: Write the failing test `tests/tools/test_reports.py`**

```python
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
    assert "metrics" not in res or res.get("metrics") in ({}, None)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/tools/test_reports.py -v`
Expected: FAIL.

- [ ] **Step 3: Write `src/gestnova_marketing/tools/reports.py`**

```python
"""Report tools. Each builds a QuerySpec with preset metrics/dimensions and
delegates to MarketingService. On no connection / failure: explicit status,
never fabricated data (golden rule)."""
from __future__ import annotations
from typing import Any

from ._base import BaseTool
from gestnova_marketing.connectors import HttpClient
from gestnova_marketing.credentials.store import CredentialStore
from gestnova_marketing.service import MarketingService, NoConnectionError
from gestnova_marketing.types import QuerySpec

_RANGE_PROPS = {
    "company_id": {"type": "string"},
    "start": {"type": "string", "format": "date"},
    "end": {"type": "string", "format": "date"},
}
_RANGE_REQUIRED = ["company_id", "start", "end"]


class _ServiceTool(BaseTool):
    def __init__(self, store: CredentialStore, http: HttpClient, *, now_iso: str) -> None:
        self._svc = MarketingService(store=store, http=http, now_iso=now_iso)

    async def _run(self, company_id: str, query: QuerySpec) -> dict[str, Any]:
        try:
            res = await self._svc.run_query(company_id, query)
        except NoConnectionError as exc:
            return {"status": "error", "error": str(exc)}
        return res.to_dict()


class SalesTool(_ServiceTool):
    name = "marketingSales"
    description = "Shopify sales for a date range (total_sales, orders). Numbers are live and carry source + range."
    input_schema = {"type": "object", "properties": _RANGE_PROPS, "required": _RANGE_REQUIRED}

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        q = QuerySpec(source="shopify", metrics=["total_sales", "orders"],
                      start=args["start"], end=args["end"])
        return await self._run(args["company_id"], q)


class TrafficTool(_ServiceTool):
    name = "marketingTraffic"
    description = "GA4 traffic for a date range (sessions, activeUsers by source). Live, with source + range."
    input_schema = {"type": "object", "properties": _RANGE_PROPS, "required": _RANGE_REQUIRED}

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        q = QuerySpec(source="ga4", metrics=["sessions", "activeUsers"],
                      dimensions=["sessionSource"], start=args["start"], end=args["end"])
        return await self._run(args["company_id"], q)


class AdsTool(_ServiceTool):
    name = "marketingAds"
    description = "Google Ads performance for a date range (cost, clicks, impressions). Live, with source + range."
    input_schema = {"type": "object", "properties": _RANGE_PROPS, "required": _RANGE_REQUIRED}

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        q = QuerySpec(source="google_ads", metrics=["cost", "clicks", "impressions"],
                      start=args["start"], end=args["end"])
        return await self._run(args["company_id"], q)
```

- [ ] **Step 4: Register the three tools in `tools/__init__.py`**

In `get_all_tools()`, after the connection tools, add the import and instances:

```python
    from .reports import SalesTool, TrafficTool, AdsTool
```
and append to the returned list:
```python
        SalesTool(store=store, http=http, now_iso=now),
        TrafficTool(store=store, http=http, now_iso=now),
        AdsTool(store=store, http=http, now_iso=now),
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/tools/test_reports.py tests/test_smoke_mcp.py -v`
Expected: all passed.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: canned report tools (sales/traffic/ads)"
```

---

## Task 12: `marketingOverview` + `marketingQuery` (flexible)

**Files:**
- Modify: `src/gestnova_marketing/tools/reports.py` (add `OverviewTool`, `QueryTool`)
- Modify: `src/gestnova_marketing/tools/__init__.py` (register them)
- Test: append to `tests/tools/test_reports.py`

- [ ] **Step 1: Append failing tests to `tests/tools/test_reports.py`**

```python
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
    assert res["sources"]["google_ads"]["status"] in ("error", "no_data")


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/tools/test_reports.py -v`
Expected: FAIL (`OverviewTool`/`QueryTool` missing).

- [ ] **Step 3: Add `OverviewTool` and `QueryTool` to `src/gestnova_marketing/tools/reports.py`**

```python
class OverviewTool(_ServiceTool):
    name = "marketingOverview"
    description = ("Unified marketing overview for a date range across all connected sources. "
                  "Missing/failed sources are reported explicitly, never invented.")
    input_schema = {"type": "object", "properties": _RANGE_PROPS, "required": _RANGE_REQUIRED}

    _PRESETS = {
        "shopify": (["total_sales", "orders"], []),
        "ga4": (["sessions", "activeUsers"], ["sessionSource"]),
        "google_ads": (["cost", "clicks", "impressions"], []),
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for source, (metrics, dims) in self._PRESETS.items():
            q = QuerySpec(source=source, metrics=metrics, dimensions=dims,
                          start=args["start"], end=args["end"])
            try:
                res = await self._svc.run_query(args["company_id"], q)
                out[source] = res.to_dict()
            except NoConnectionError as exc:
                out[source] = {"status": "error", "error": str(exc), "metrics": {}}
        return {"status": "ok", "date_range": {"start": args["start"], "end": args["end"]},
                "sources": out}


class QueryTool(_ServiceTool):
    name = "marketingQuery"
    description = ("Flexible query: pick source, metrics, dimensions, date range, filters. "
                  "For custom cross-cuts not covered by the canned reports.")
    input_schema = {
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "source": {"type": "string", "enum": ["shopify", "ga4", "google_ads"]},
            "metrics": {"type": "array", "items": {"type": "string"}},
            "dimensions": {"type": "array", "items": {"type": "string"}},
            "start": {"type": "string", "format": "date"},
            "end": {"type": "string", "format": "date"},
            "filters": {"type": "object"},
        },
        "required": ["company_id", "source", "metrics", "start", "end"],
    }

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        q = QuerySpec(source=args["source"], metrics=args["metrics"],
                      dimensions=args.get("dimensions", []),
                      start=args["start"], end=args["end"],
                      filters=args.get("filters", {}))
        return await self._run(args["company_id"], q)
```

- [ ] **Step 4: Register both in `tools/__init__.py`**

Extend the reports import and append instances:
```python
    from .reports import SalesTool, TrafficTool, AdsTool, OverviewTool, QueryTool
```
```python
        OverviewTool(store=store, http=http, now_iso=now),
        QueryTool(store=store, http=http, now_iso=now),
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/tools/test_reports.py -v`
Expected: all passed.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: marketingOverview + flexible marketingQuery tools"
```

---

## Task 13: Golden-rule hardening (no-invention propagation across the stack)

**Files:**
- Create: `tests/tools/test_no_invention.py`

This task adds no new behavior — it pins the golden rule end-to-end so regressions are caught.

- [ ] **Step 1: Write `tests/tools/test_no_invention.py`**

```python
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
```

- [ ] **Step 2: Run the full suite**

Run: `uv run pytest -v`
Expected: all tests pass (Tasks 1-13).

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "test: pin golden-rule no-invention propagation end-to-end"
```

---

## Task 14: HTTP server parity entrypoint

**Files:**
- Create: `src/gestnova_marketing/http_server.py`
- Test: `tests/test_http_server.py`

Mirrors `gestnova-accounting`'s HTTP entrypoint so the agent can load this MCP the
same way it loads the others (wiring later).

- [ ] **Step 1: Write the failing test `tests/test_http_server.py`**

```python
import pytest
from fastapi.testclient import TestClient
from gestnova_marketing.http_server import build_app


def test_list_tools_endpoint_lists_marketing_tools():
    client = TestClient(build_app())
    resp = client.get("/tools")
    assert resp.status_code == 200
    names = [t["name"] for t in resp.json()["tools"]]
    assert "ping" in names
    assert "marketingSales" in names
    assert "marketingQuery" in names


def test_call_ping_over_http():
    client = TestClient(build_app())
    resp = client.post("/call", json={"name": "ping", "arguments": {}})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_http_server.py -v`
Expected: FAIL.

- [ ] **Step 3: Write `src/gestnova_marketing/http_server.py`**

```python
"""HTTP entrypoint (parity with other gestnova-*-mcp servers)."""
from __future__ import annotations
from fastapi import FastAPI
from pydantic import BaseModel

from gestnova_marketing.server import build_server


class CallRequest(BaseModel):
    name: str
    arguments: dict = {}


def build_app() -> FastAPI:
    app = FastAPI(title="gestnova-marketing-mcp")
    server = build_server()

    @app.get("/tools")
    async def list_tools():
        tools = await server.list_tools()
        return {"tools": [
            {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
            for t in tools
        ]}

    @app.post("/call")
    async def call(req: CallRequest):
        return await server.call_tool(req.name, req.arguments)

    return app


def main():
    import os
    import uvicorn
    uvicorn.run(build_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8020")))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_http_server.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: HTTP server parity entrypoint"
```

---

## Task 15: README integration doc + Dockerfile + final full run

**Files:**
- Create: `README.md`, `Dockerfile`

- [ ] **Step 1: Write `README.md`** (this is the spec §6.1 "integration README")

````markdown
# gestnova-marketing-mcp

MCP server that lets a Gestnova agent read and analyze a company's marketing data
(Shopify sales, GA4 traffic, Google Ads) per-tenant. **Read/analyze only** in v1;
platform control (write actions) is a documented Phase 2.

## Status
Standalone MCP — **not yet wired into the agent**. See "Integration" below.

## Run
```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest -v                       # full test suite
uv run gestnova-marketing-mcp          # stdio MCP server
uv run gestnova-marketing-http         # HTTP server (PORT, default 8020)
```

## Environment
| Var | Purpose |
|---|---|
| `MARKETING_CRED_KEY` | Fernet key for encrypting stored tokens (file store) |
| `MARKETING_CRED_PATH` | Path to the encrypted credential file (file store) |
| `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET` | Shopify OAuth app |
| `GA4_CLIENT_ID` / `GA4_CLIENT_SECRET` | Google OAuth client (GA4) |
| `GOOGLE_ADS_CLIENT_ID` / `GOOGLE_ADS_CLIENT_SECRET` | Google OAuth client (Ads) |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Gestnova MCC developer token (Basic/Standard access) |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | Gestnova MCC customer id |

If `MARKETING_CRED_KEY`/`PATH` are unset, an in-memory store is used (dev only).

## Tools
| Tool | Purpose |
|---|---|
| `ping` | health check |
| `marketingConnectAccount` | start OAuth → returns authorization URL |
| `marketingCompleteConnection` | exchange code → store token for the company |
| `marketingListConnections` | list a company's connections |
| `marketingSales` | Shopify sales for a range |
| `marketingTraffic` | GA4 traffic for a range |
| `marketingAds` | Google Ads performance for a range |
| `marketingOverview` | unified view across connected sources |
| `marketingQuery` | flexible custom query (metrics/dimensions/filters) |

Every data tool returns `source`, `account_id`, `date_range`, `fetched_at`,
`status` (`ok`/`no_data`/`error`). **Golden rule:** on failure or no data the tool
says so — it never fabricates numbers.

## Integration (Phase: wiring — separate session)
To wire into the Gestnova agent later:
1. Register this server in the agent's MCP config (stdio: `gestnova-marketing-mcp`,
   or HTTP: `gestnova-marketing-http`), exactly like `gestnova-accounting-mcp`.
2. Back `CredentialStore` with Gestnova's Postgres by adding a
   `PostgresCredentialStore(CredentialStore)` impl and selecting it in
   `tools/__init__._build_store()` — no other code changes (drop-in).
3. The agent passes its `company_id` into every tool call (tenant isolation).
4. Expose the tools in the webOS chat/voice surface and connect to the kernel via
   the existing connectors.
5. After each query, have the agent persist a snapshot + insight into its memory
   for continuity.

## Phase 2 (not built)
Write actions (pause/activate campaign, change budget, publish). Requires write
OAuth scopes + stricter App Review. **Always behind explicit human confirmation.**
````

- [ ] **Step 2: Write `Dockerfile`** (parity with accounting-mcp)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
COPY src ./src
RUN uv pip install --system -e .
EXPOSE 8020
CMD ["gestnova-marketing-http"]
```

- [ ] **Step 3: Run the complete suite + ruff + import check**

Run: `uv run pytest -v && uv run ruff check src tests && uv run python -c "import gestnova_marketing.connectors as c; import gestnova_marketing.connectors.shopify, gestnova_marketing.connectors.ga4, gestnova_marketing.connectors.google_ads; print(c.supported_sources())"`
Expected: all tests pass; ruff clean; prints `['ga4', 'google_ads', 'shopify']`.

- [ ] **Step 4: Final commit**

```bash
git add -A && git commit -m "docs: integration README + Dockerfile; v1 complete (standalone, unwired)"
```

---

## Done criteria (maps to spec §9)

- [ ] MCP starts over stdio and lists all tools; no dependency on the agent runtime.
- [ ] A company can connect Shopify/GA4 (connect → complete → token stored encrypted).
- [ ] Calling tools directly yields real metrics with `source`/`account_id`/`date_range`/`fetched_at`.
- [ ] `marketingQuery` resolves a custom cross-cut (e.g. conversions by city).
- [ ] Tenant isolation proven: company A's calls never read company B's data/tokens.
- [ ] API failure / no data → `status: error|no_data` with reason, never invented numbers.
- [ ] README documents the future wiring to the agent + webOS kernel.

> Out of v1 (validated at integration time): OnlyOffice doc generation, conversational/voice delivery, scheduled Monday report, memory snapshot writeback. Phase 2: write actions.
