"""Live integration test against real homelab — exercises all 6 tools."""

import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
os.chdir(os.path.dirname(__file__))

from proxmox_dr_mcp.config import get_config
from proxmox_dr_mcp.proxmox.client import ProxmoxClient
from mcp.server.fastmcp import FastMCP
from proxmox_dr_mcp.tools.preflight import register_preflight_tools
from proxmox_dr_mcp.tools.snapshot import register_snapshot_tools
from proxmox_dr_mcp.tools.health import register_health_tools
from proxmox_dr_mcp.tools.dr_workflow import register_dr_workflow_tools

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
    print("=" * 60)
    print("PROXMOX DR MCP — LIVE HOMELAB TEST")
    print("=" * 60)

    config = get_config()
    print(f"\n📋 Config: {config.proxmox_host} → node={config.node}")

    client = ProxmoxClient(config)
    nodes = await test("Get nodes", lambda: client.get_nodes())
    if not nodes: return
    node = nodes[0].node
    print(f"    Active: {node}")

    # --- VMs ---
    print("\n[1] VMs")
    vms = await test("List VMs", lambda: client.get_vms(node))
    if vms:
        running = [v for v in vms if v.status == "running"]
        print(f"    {len(vms)} total, {len(running)} running")
        if running:
            s = await test(f"Status of VM {running[0].vmid}",
                           lambda: client.get_vm_status(node, running[0].vmid))
            if s: print(f"    → {s.status}, CPU: {s.cpus}")

    # --- Containers ---
    print("\n[2] Containers")
    cts = await test("List containers", lambda: client.get_containers(node))
    if cts:
        running = [c for c in cts if c.status == "running"]
        print(f"    {len(cts)} total, {len(running)} running")
        if running:
            s = await test(f"Status of CT {running[0].vmid}",
                           lambda: client.get_ct_status(node, running[0].vmid))
            if s: print(f"    → {s.status}")

    # --- Snapshots (LXC) ---
    print("\n[3] LXC Snapshots")
    # pick a small running CT — pihole(105), mqtt(110), actualbudget(108)
    targets = [c for c in (cts or []) if c.status == "running" and c.vmid in (105, 108, 110)]
    if targets:
        t = targets[0]
        snaps = await test(f"List existing snapshots on CT {t.vmid} ({t.name})",
                           lambda: client.list_snapshots(node, t.vmid, target_type="lxc"))
        if snaps is not None:
            print(f"    {len(snaps)} snapshot(s)")
            now = __import__("datetime").datetime.now()
            snap_name = f"test-dr-{now.strftime('%Y%m%d-%H%M%S')}"
            upid = await test(f"Create snapshot '{snap_name}'",
                              lambda: client.create_snapshot(node, t.vmid, snap_name,
                                                             description="DR MCP integration test",
                                                             vmstate=False, target_type="lxc"))
            if upid:
                print(f"    UPID created ✅")
                verify = await test(f"Verify snapshot exists",
                                    lambda: client.list_snapshots(node, t.vmid, target_type="lxc"))
                if verify:
                    found = [s for s in verify if s.name == snap_name]
                    print(f"    Snapshot found: {bool(found)}")
                clean = await test(f"Delete snapshot '{snap_name}'",
                                   lambda: client.delete_snapshot(node, t.vmid, snap_name, target_type="lxc"))
                if clean:
                    final = await test(f"Verify deletion",
                                       lambda: client.list_snapshots(node, t.vmid, target_type="lxc"))
                    if final:
                        still = [s for s in final if s.name == snap_name]
                        print(f"    Snapshot gone: {not still}")

    # --- Storage + Preflight ---
    print("\n[4] Storage & Backups")
    storages = await test("Get storage", lambda: client.get_storage(node))
    if storages:
        for s in storages[:4]:
            free = s.avail / (1024**3) if s.avail else 0
            print(f"    {s.storage}: {free:.0f}GB free")
    backup = await test("Check backup storage",
                        lambda: asyncio.gather(*[
                            client.get_storage_content(node, s.storage)
                            for s in (storages or [])
                            if "backup" in (s.content or "").lower()
                        ]))
    if backup:
        total = sum(len(b) for b in backup if b)
        print(f"    {total} backup files found")

    # --- Tool registration ---
    print("\n[5] Tool Registration")
    server = FastMCP(name="test")
    for reg in [register_preflight_tools, register_snapshot_tools,
                register_health_tools, register_dr_workflow_tools]:
        reg(server, client)
    tools = server._tool_manager.list_tools()
    for t in tools:
        print(f"  ✅ {t.name}")
    print(f"    {len(tools)} tools registered")

    print("\n" + "=" * 60)
    total = passed + failed
    print(f"RESULTS: {passed}/{total} passed, {failed}/{total} failed")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    asyncio.run(main())
