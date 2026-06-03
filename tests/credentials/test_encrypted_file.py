from pathlib import Path

from cryptography.fernet import Fernet

from gestnova_marketing.credentials.encrypted_file import EncryptedFileCredentialStore
from gestnova_marketing.credentials.store import Connection


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
