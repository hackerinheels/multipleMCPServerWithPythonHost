import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from starlette.applications import Starlette
from sse_starlette.sse import EventSourceResponse

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn


#Server Name and Description
xMCP = FastMCP("Add numbers")
#any additional configuration

#any additional helper functions
def addNumbers(x: int, y: int) -> int:
    """Add two numbers together."""
    try:
        return x + y

    except Exception as e:
        print(f"Error in addNumbers: {str(e)}")
        raise

@xMCP.tool("addNumbers")
async def addNumbers(x: int, y: int) -> int:
    """Add two numbers together."""
    try:
        return x + y
        
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}

def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can server the provied mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


if __name__ == "__main__":
    mcp_server = xMCP._mcp_server  # noqa: WPS437
    import argparse
    parser = argparse.ArgumentParser(description='Run MCP SSE-based server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8081, help='Port to listen on')
    args = parser.parse_args()

    # Bind SSE request handling to MCP server
    starlette_app = create_starlette_app(mcp_server, debug=True)

    uvicorn.run(starlette_app, host=args.host, port=args.port)
