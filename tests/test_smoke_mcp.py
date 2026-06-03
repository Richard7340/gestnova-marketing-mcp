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
