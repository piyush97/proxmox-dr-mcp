"""FastMCP server for Proxmox DR tools — HTTP transport for MCPize deployment."""

from __future__ import annotations

import logging
import sys
import os
from os import getenv

from fastmcp import FastMCP

from proxmox_dr_mcp.config import get_config
from proxmox_dr_mcp.proxmox.client import ProxmoxClient
from proxmox_dr_mcp.tools.preflight import register_preflight_tools
from proxmox_dr_mcp.tools.snapshot import register_snapshot_tools
from proxmox_dr_mcp.tools.health import register_health_tools
from proxmox_dr_mcp.tools.dr_workflow import register_dr_workflow_tools

logger = logging.getLogger(__name__)


def create_server() -> FastMCP:
    """Create and configure the FastMCP server with all tools.

    NOTE: Config validation is deferred to tool execution time.
    The server starts even without PROXMOX_HOST/token set.
    Tools will return meaningful errors if credentials are missing.
    """
    logging.basicConfig(
        level=getattr(logging, getenv("LOG_LEVEL", "INFO"), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    logger.info("Creating Proxmox DR MCP server...")

    server = FastMCP(name="proxmox-dr-mcp")

    # Create client lazily — config will be validated at tool call time
    try:
        config = get_config()
        client = ProxmoxClient(config)
        logger.info(f"Proxmox config loaded: {config.proxmox_host}")
    except Exception as e:
        logger.warning(f"Proxmox config not available at startup: {e}")
        logger.warning("Tools will return errors until PROXMOX_HOST/TOKEN vars are set.")
        client = None

    register_preflight_tools(server, client)
    register_snapshot_tools(server, client)
    register_health_tools(server, client)
    register_dr_workflow_tools(server, client)

    logger.info(f"Server '{server.name}' ready with all tools registered.")
    return server


def main() -> None:
    """Main entry point — runs the HTTP MCP server."""
    port = int(getenv("PORT", "8080"))

    logger.info(f"Proxmox DR MCP server starting on port {port}...")
    server = create_server()

    # Health check endpoint
    @server.get("/health")
    async def health():
        return {"status": "healthy", "server": "proxmox-dr-mcp"}

    server.run(transport="streamable-http", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
