"""HTTP entrypoint (parity with other gestnova-*-mcp servers)."""
from __future__ import annotations
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from gestnova_marketing.server import build_server


class CallRequest(BaseModel):
    name: str
    arguments: dict


def build_app() -> FastAPI:
    app = FastAPI(title="gestnova-marketing-mcp")
    server = build_server()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/tools")
    async def list_tools():
        tools = await server.list_tools()
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]

    @app.post("/call")
    async def call(req: CallRequest):
        try:
            return await server.call_tool(req.name, req.arguments)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    return app


def main():
    import os
    import uvicorn
    uvicorn.run(build_app(), host="127.0.0.1", port=int(os.environ.get("PORT", "8020")))


if __name__ == "__main__":
    main()
