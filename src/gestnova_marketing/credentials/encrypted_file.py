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
