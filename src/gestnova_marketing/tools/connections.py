"""Connection lifecycle tools: build auth URL, exchange code, list connections."""
from __future__ import annotations
import os
from typing import Any
from urllib.parse import urlencode

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
        client_id = os.environ.get(f"{source.upper()}_CLIENT_ID", "")
        params = {
            "client_id": client_id,
            "redirect_uri": args["redirect_uri"],
            "response_type": "code",
            "scope": meta["scope"],
            "state": args["company_id"],
        }
        url = f"{auth}?{urlencode(params)}"
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
