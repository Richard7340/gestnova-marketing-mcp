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
