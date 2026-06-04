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

Per-source OAuth client id/secret are read as `<SOURCE>_CLIENT_ID` /
`<SOURCE>_CLIENT_SECRET` (source upper-cased: `SHOPIFY_`, `GA4_`, `GOOGLE_ADS_`).
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

`marketingQuery` filters: GA4 supports equality dimension filters (e.g.
`{"city": "Madrid"}`, applied as an EXACT-match `dimensionFilter`). The Shopify
and Google Ads connectors **reject** non-empty filters in v1 with a
`status: error` reason rather than silently ignoring them.

## HTTP server
`gestnova-marketing-http` mirrors the `gestnova-accounting-mcp` contract
(FastAPI, binds `127.0.0.1`, default `PORT=8020`):
- `GET /health` → `{"status": "ok"}`
- `GET /tools` → bare JSON list of `{name, description, input_schema}`
- `POST /call` with `{"name": ..., "arguments": {...}}` → tool result
- unknown tool name → HTTP `404`

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
