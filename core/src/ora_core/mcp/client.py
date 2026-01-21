import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .registry import tool_registry, ToolDefinition

logger = logging.getLogger(__name__)

class MCPClientManager:
    """
    Manages connections to external MCP servers and registers their tools into ORA Core.
    """
    def __init__(self):
        # server_name -> session
        self.sessions: Dict[str, ClientSession] = {}
        # server_name -> exit_stack (to clean up stdio)
        self.exit_stacks: Dict[str, Any] = {}

    async def connect_stdio(self, server_name: str, command: str, args: List[str] = [], env: Dict[str, str] = {}):
        """
        Connect to an MCP server via stdio and register its tools.
        """
        logger.info(f"Connecting to MCP server '{server_name}' via stdio: {command} {' '.join(args)}")
        
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env={**env, "PATH": f"{env.get('PATH', '')};{os.environ.get('PATH', '')}"} if os.name == 'nt' else env
        )

        try:
            # We use an ExitStack pattern to manage the lifetime of the stdio transport
            from contextlib import AsyncExitStack
            stack = AsyncExitStack()
            self.exit_stacks[server_name] = stack
            
            read, write = await stack.enter_async_context(stdio_client(server_params))
            session = await stack.enter_async_context(ClientSession(read, write))
            
            await session.initialize()
            self.sessions[server_name] = session
            
            # Register Tools
            await self._register_tools(server_name)
            logger.info(f"Successfully connected and registered tools from '{server_name}'")
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{server_name}': {e}", exc_info=True)
            if server_name in self.exit_stacks:
                await self.exit_stacks[server_name].aclose()
                del self.exit_stacks[server_name]
            raise

    async def _register_tools(self, server_name: str):
        session = self.sessions.get(server_name)
        if not session:
            return

        result = await session.list_tools()
        tools = result.tools
        
        for tool in tools:
            # MCP Tool -> ORA ToolDefinition
            # Note: MCP 'inputSchema' is a full JSON schema.
            # ORA ToolDefinition expects 'parameters' as the 'properties' part or full schema?
            # Looking at OmniEngine, it expects t.parameters to be the full schema.
            
            def create_handler(t_name, s_name):
                # We need to capture variables in closure
                async def handler(args, context):
                    target_session = self.sessions.get(s_name)
                    if not target_session:
                        raise RuntimeError(f"MCP Session for '{s_name}' lost.")
                    
                    mcp_res = await target_session.call_tool(t_name, args)
                    
                    # Convert MCP CallToolResult to ORA standardized result
                    # MCP content is a list of TextContent/ImageContent/etc.
                    content_list = []
                    for item in mcp_res.content:
                        if hasattr(item, 'text'):
                            content_list.append({"type": "text", "text": item.text})
                        # Add image support later
                    
                    return {
                        "ok": not mcp_res.isError,
                        "content": content_list,
                        "metrics": {"source": f"mcp:{s_name}"}
                    }
                return handler

            handler = create_handler(tool.name, server_name)
            ora_def = ToolDefinition(
                name=f"{server_name}_{tool.name}", # Namespace to avoid collisions
                description=tool.description or "",
                parameters=tool.inputSchema, # JSON Schema
                allowed_clients=["web", "discord", "api"],
                timeout_sec=60
            )
            
            tool_registry.register_tool(ora_def, handler)
            logger.info(f"Registered MCP tool: {ora_def.name}")

    async def shutdown(self):
        for name, stack in self.exit_stacks.items():
            logger.info(f"Closing MCP server '{name}'")
            await stack.aclose()
        self.sessions.clear()
        self.exit_stacks.clear()

# Singleton instance
mcp_client_manager = MCPClientManager()

import os # Required for PATH expansion in connect_stdio
