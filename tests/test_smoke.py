"""Smoke test — verify tool registration works (sync)."""

import asyncio
from fastmcp import FastMCP
from proxmox_dr_mcp.tools.preflight import register_preflight_tools
from proxmox_dr_mcp.tools.snapshot import register_snapshot_tools
from proxmox_dr_mcp.tools.health import register_health_tools
from proxmox_dr_mcp.tools.dr_workflow import register_dr_workflow_tools


async def _test_tool_registration():
    server = FastMCP(name="smoke-test")
    register_preflight_tools(server, None)
    register_snapshot_tools(server, None)
    register_health_tools(server, None)
    register_dr_workflow_tools(server, None)

    tools = await server._tool_manager.get_tools()
    print(f"✅ {len(tools)} tools registered")
    for t in tools:
        print(f"   - {t}")

    assert len(tools) == 6, f"Expected 6 tools, got {len(tools)}"
    print("✅ All assertions passed")
    return tools


def test_tool_registration():
    return asyncio.run(_test_tool_registration())


if __name__ == "__main__":
    test_tool_registration()
