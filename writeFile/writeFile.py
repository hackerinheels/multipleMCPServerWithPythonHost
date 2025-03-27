from typing import Any, Dict, List 
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from sse_starlette.sse import EventSourceResponse
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn
import os
# Initialize FastMCP server
mcp = FastMCP("Write content to a file")


@mcp.tool("write_to_csv_file")
async def writefile_content(file_path: str, content: str):
    """
    Writes content to a csv file.
    """
    print("Did I come here?")
    parentDir = os.path.dirname(os.getcwd())
    currentDir = os.path.basename(os.getcwd())
    file_path = os.path.join(parentDir, currentDir, file_path)
    print("writing to " , file_path)

    with open(file_path, 'w') as file:
        file.write(content)




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
    mcp_server = mcp._mcp_server  # noqa: WPS437
    import argparse
    parser = argparse.ArgumentParser(description='Run MCP SSE-based server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8081, help='Port to listen on')
    args = parser.parse_args()

    # Bind SSE request handling to MCP server
    starlette_app = create_starlette_app(mcp_server, debug=True)

    uvicorn.run(starlette_app, host=args.host, port=args.port)
