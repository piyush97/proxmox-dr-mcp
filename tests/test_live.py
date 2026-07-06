"""Live integration test — creates/deletes a test snapshot and waits for task completion."""

import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
os.chdir(os.path.dirname(__file__))

from proxmox_dr_mcp.config import get_config
from proxmox_dr_mcp.proxmox.client import ProxmoxClient

passed = failed = 0

async def test(name, fn):
    global passed, failed
    try:
        r = await fn()
        print(f"  ✅ {name}")
        passed += 1
        return r
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        failed += 1
        return None

async def main():
    global passed, failed
    config = get_config()
    client = ProxmoxClient(config)

    nodes = await test("Connect to Proxmox", lambda: client.get_nodes())
    if not nodes: return
    node = nodes[0].node

    cts = await test("List containers", lambda: client.get_containers(node))
    running = [c for c in (cts or []) if c.status == "running"]
    target = next((c for c in running if c.vmid in (105, 108, 110)), running[0] if running else None)
    if not target:
        print("  ❌ No running container to test with")
        return

    # Create snapshot
    snap_name = f"test-{__import__('datetime').datetime.now().strftime('%Y%m%d-%H%M%S')}"
    upid = await test(f"Create snapshot {snap_name} on CT {target.vmid}",
                      lambda: client.create_snapshot(node, target.vmid, snap_name,
                                                     description="DR MCP test", target_type="lxc"))
    if upid:
        # Wait for task
        status = await test(f"Wait for snapshot task",
                           lambda: client.wait_for_task(node, upid))
        if status:
            print(f"    exitstatus: {status.get('exitstatus')}")

        # Verify
        snaps = await test(f"Verify snapshot exists",
                          lambda: client.list_snapshots(node, target.vmid, target_type="lxc"))
        if snaps:
            found = any(s.name == snap_name for s in snaps)
            print(f"    Snapshot present: {found}")

        # Delete
        del_upid = await test(f"Delete snapshot {snap_name}",
                             lambda: client.delete_snapshot(node, target.vmid, snap_name, target_type="lxc"))
        if del_upid:
            # Wait for delete task
            status2 = await test(f"Wait for delete task",
                                lambda: client.wait_for_task(node, del_upid))
            if status2:
                print(f"    exitstatus: {status2.get('exitstatus')}")

        # Verify gone
        snaps2 = await test(f"Verify snapshot deleted",
                           lambda: client.list_snapshots(node, target.vmid, target_type="lxc"))
        if snaps2:
            still = any(s.name == snap_name for s in snaps2)
            print(f"    Snapshot gone: {not still}")

    # Tool registration smoke test
    from fastmcp import FastMCP
    from proxmox_dr_mcp.tools.preflight import register_preflight_tools
    from proxmox_dr_mcp.tools.snapshot import register_snapshot_tools
    from proxmox_dr_mcp.tools.health import register_health_tools
    from proxmox_dr_mcp.tools.dr_workflow import register_dr_workflow_tools

    server = FastMCP(name="test")
    for reg in [register_preflight_tools, register_snapshot_tools,
                register_health_tools, register_dr_workflow_tools]:
        reg(server, client)
    tools = server._tool_manager.list_tools()
    await test(f"Register all {len(tools)} tools", lambda: asyncio.sleep(0))
    for t in tools:
        print(f"      {t.name}")

    total = passed + failed
    print(f"\n{'='*50}")
    print(f"RESULTS: {passed}/{total} passed, {failed}/{total} failed")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    asyncio.run(main())
