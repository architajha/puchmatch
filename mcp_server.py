# mcp_server.py
import os
import asyncio
from dotenv import load_dotenv
import httpx
import uvicorn
from mcp.server import Server
from mcp.types import ToolResult  # depends on mcp package version; adjust if needed
import logging

# load env (will pick up AUTH_TOKEN, OWNER_PHONE from your .env)
load_dotenv()
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "changeme")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_BASE = f"http://localhost:{API_PORT}"  # FastAPI address used by bridge

# Import FastAPI app (your existing main.py must be in same folder / importable)
import main as main_app_module  # noqa: E402
app = main_app_module.app

# create MCP server (bridge)
mcp = Server(name="PuchMatch MCP Bridge")

# helper to call your HTTP endpoints
async def call_api(method: str, endpoint: str, json=None, params=None):
    url = f"{API_BASE}{endpoint}"
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    # small retry/backoff could be added here
    async with httpx.AsyncClient(timeout=10.0) as client:
        if method.lower() == "post":
            resp = await client.post(url, json=json, headers=headers)
        elif method.lower() == "get":
            resp = await client.get(url, params=params, headers=headers)
        else:
            raise ValueError("unsupported method")
    try:
        return resp.json()
    except Exception:
        return {"status_code": resp.status_code, "text": resp.text}


# Define MCP tools that proxy to HTTP endpoints
@mcp.tool()
async def validate() -> ToolResult:
    return await call_api("post", "/validate")


@mcp.tool()
async def join_chat(user_id: str, nickname: str = None) -> ToolResult:
    payload = {"user_id": user_id, "nickname": nickname}
    return await call_api("post", "/join_chat", json=payload)


@mcp.tool()
async def send_message(user_id: str, text: str) -> ToolResult:
    payload = {"user_id": user_id, "text": text}
    return await call_api("post", "/send_message", json=payload)


@mcp.tool()
async def get_messages(user_id: str) -> ToolResult:
    return await call_api("get", "/get_messages", params={"user_id": user_id})


@mcp.tool()
async def skip_user(user_id: str) -> ToolResult:
    return await call_api("post", "/skip", json={"user_id": user_id})


@mcp.tool()
async def leave(user_id: str) -> ToolResult:
    return await call_api("post", "/leave", json={"user_id": user_id})


@mcp.tool()
async def status(user_id: str) -> ToolResult:
    return await call_api("get", "/status", params={"user_id": user_id})


# Run uvicorn programmatically + MCP server (stdio)
async def run_uvicorn():
    """Run FastAPI app (main.app) via uvicorn programmatically so both run in same process."""
    config = uvicorn.Config(app, host=API_HOST, port=API_PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()  # returns when server stops


async def main():
    logging.basicConfig(level=logging.INFO)
    # start uvicorn in a background task
    uvicorn_task = asyncio.create_task(run_uvicorn())
    # give uvicorn a moment to start before MCP begins handling calls
    await asyncio.sleep(0.5)

    # Run the MCP server over stdio (this blocks until stdio server stops)
    # Many MCP clients expect stdio. If you need TCP/WS instead, see note below.
    await mcp.run_stdio()

    # If MCP stops, shut down uvicorn
    uvicorn_task.cancel()
    try:
        await uvicorn_task
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down.")
