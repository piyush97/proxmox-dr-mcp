"""FastMCP server for Proxmox DR tools."""

from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

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

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    logger.info("Creating Proxmox DR MCP server...")
    logger.info(f"Target node: {config.node}")
    logger.info(f"Snapshot prefix: {config.default_snapshot_prefix}")

    # Create FastMCP server
    server = FastMCP(
        name="proxmox-dr-mcp",
    )

    # Create Proxmox client
    client = ProxmoxClient(config)

    # Register all tool groups
    register_preflight_tools(server, client)
    register_snapshot_tools(server, client)
    register_health_tools(server, client)
    register_dr_workflow_tools(server, client)

    logger.info(f"MCP server '{server.name}' ready with all tools registered.")
    return server


def main() -> None:
    """Main entry point — validates config and runs the server."""
    try:
        config = get_config()
        if not config.proxmox_host:
            print("ERROR: PROXMOX_HOST is required. Set env vars or create a .env file.", file=sys.stderr)
            sys.exit(1)
        if not config.proxmox_token_id or not config.proxmox_token_value:
            print("ERROR: PROXMOX_TOKEN_ID and PROXMOX_TOKEN_VALUE are required.", file=sys.stderr)
            sys.exit(1)

        logger.info("Proxmox DR MCP server starting...")
        server = create_server()
        server.run(transport="stdio")
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
