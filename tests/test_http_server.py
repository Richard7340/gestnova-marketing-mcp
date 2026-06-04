from fastapi.testclient import TestClient
from gestnova_marketing.http_server import build_app


def test_health_endpoint():
    client = TestClient(build_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_tools_endpoint_lists_marketing_tools():
    client = TestClient(build_app())
    resp = client.get("/tools")
    assert resp.status_code == 200
    names = [t["name"] for t in resp.json()]
    assert "ping" in names
    assert "marketingSales" in names
    assert "marketingQuery" in names


def test_tools_use_input_schema_key():
    client = TestClient(build_app())
    resp = client.get("/tools")
    assert resp.status_code == 200
    for tool in resp.json():
        assert "input_schema" in tool


def test_call_ping_over_http():
    client = TestClient(build_app())
    resp = client.post("/call", json={"name": "ping", "arguments": {}})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_call_unknown_tool_returns_404():
    client = TestClient(build_app())
    resp = client.post("/call", json={"name": "doesNotExist", "arguments": {}})
    assert resp.status_code == 404
