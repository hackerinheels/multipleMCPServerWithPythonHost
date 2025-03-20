from typing import Any, Dict, List 
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn

# Initialize FastMCP server
mcp = FastMCP("Jackie and Shadow eagle feed")


@mcp.tool()
async def get_eagle_feed() -> List[Dict[str, str]]:
    """
    Returns information about the live bald eagle cam feeds for Jackie and Shadow
    Each feed includes location, link to the live feed, and a description.
    """
    eagle_feeds = [
        {
            "location": "Big Bear Valley, California",
            "link": "https://www.youtube.com/watch?v=B4-L2nfGcuE",
            "description": "This nest is home to the famous bald eagle pair Jackie and Shadow in Big Bear Valley, California. The Friends of Big Bear Valley maintain this popular live cam that has documented multiple nesting seasons. The nest is located in a Jeffrey Pine tree near Big Bear Lake in the San Bernardino Mountains."
        }
    ]
    
    return eagle_feeds

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
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    args = parser.parse_args()

    # Bind SSE request handling to MCP server
    starlette_app = create_starlette_app(mcp_server, debug=True)

    uvicorn.run(starlette_app, host=args.host, port=args.port)

