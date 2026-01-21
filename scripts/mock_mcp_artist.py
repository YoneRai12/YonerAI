import asyncio
import sys
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# Create a server
server = Server("mcp-artist")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="generate_artwork",
            description="Generate a beautiful artwork based on a prompt.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The description of the artwork."},
                },
                "required": ["prompt"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls."""
    if name == "generate_artwork":
        prompt = arguments.get("prompt", "unknown")
        # Mock result
        return [
            types.TextContent(
                type="text",
                text=f"Artwork generated for: {prompt}. (This is a mock result from mcp-artist)"
            )
        ]
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with stdio_server() as (read, write):
        await server.run(
            read,
            write,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
