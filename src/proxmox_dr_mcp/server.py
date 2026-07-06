"""FastMCP server for Proxmox DR tools — HTTP transport for MCPize deployment."""

from __future__ import annotations

import logging
import signal
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
    """Create and configure the FastMCP server with all tools."""
    config = get_config()

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    logger.info("Creating Proxmox DR MCP server...")
    logger.info(f"Target node: {config.node}")
    logger.info(f"Snapshot prefix: {config.default_snapshot_prefix}")

    server = FastMCP(name="proxmox-dr-mcp")
    client = ProxmoxClient(config)

    register_preflight_tools(server, client)
    register_snapshot_tools(server, client)
    register_health_tools(server, client)
    register_dr_workflow_tools(server, client)

    logger.info(f"Server '{server.name}' ready with all tools registered.")
    return server


def main() -> None:
    """Main entry point — runs the HTTP MCP server."""
    port = int(getenv("PORT", "8080"))

    try:
        config = get_config()
        if not config.proxmox_host:
            print("ERROR: PROXMOX_HOST is required.", file=sys.stderr)
            sys.exit(1)
        if not config.proxmox_token_id or not config.proxmox_token_value:
            print("ERROR: PROXMOX_TOKEN_ID and PROXMOX_TOKEN_VALUE are required.", file=sys.stderr)
            sys.exit(1)

        logger.info(f"Proxmox DR MCP server starting on port {port}...")
        server = create_server()
        server.run(transport="streamable-http", host="0.0.0.0", port=port)
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
