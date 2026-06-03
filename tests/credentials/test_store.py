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
