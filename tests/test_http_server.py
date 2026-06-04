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
