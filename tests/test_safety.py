"""Focused checks for DR safety gates; run with ``uv run python tests/test_safety.py``."""

import asyncio
from time import time

from fastmcp import FastMCP

from proxmox_dr_mcp.proxmox.client import ProxmoxClient
from proxmox_dr_mcp.proxmox.exceptions import TaskError
from proxmox_dr_mcp.proxmox.models import Node, Storage, VMStatus
from proxmox_dr_mcp.tools.dr_workflow import register_dr_workflow_tools
from proxmox_dr_mcp.tools.preflight import run_preflight


class FakeClient:
    def __init__(self, *, free_gb: int = 10, backup_age_days: int = 1) -> None:
        self.free_gb = free_gb
        self.backup_age_days = backup_age_days
        self.snapshot_calls = 0
        self.wait_calls = 0

    async def get_nodes(self):
        return [Node(node="pve", status="online")]

    async def get_storage(self, node):
        return [Storage(storage="local", type="dir", content="backup", avail=self.free_gb * 1024**3)]

    async def get_storage_content(self, node, storage):
        return [{"volid": "local:backup/vzdump-qemu-100.vma.zst", "ctime": time() - self.backup_age_days * 86400}]

    async def get_vms(self, node):
        return [VMStatus(vmid=100, name="app", status="running", node=node)]

    async def get_containers(self, node):
        return []

    async def create_snapshot(self, **kwargs):
        self.snapshot_calls += 1
        return "UPID:ok"

    async def wait_for_task(self, node, upid, timeout):
        self.wait_calls += 1
        return {"status": "stopped", "exitstatus": "OK"}


async def main() -> None:
    stale = await run_preflight(FakeClient(backup_age_days=8))
    assert not stale.passed and not stale.has_recent_backups

    blocked_client = FakeClient(free_gb=4)
    blocked = await _safe_upgrade(blocked_client)
    assert not blocked["success"] and blocked_client.snapshot_calls == 0

    ready_client = FakeClient()
    ready = await _safe_upgrade(ready_client)
    assert ready["success"] and ready_client.wait_calls == 1
    assert all(step["name"] != "health_check" for step in ready["steps"])

    task_client = object.__new__(ProxmoxClient)

    async def stopped_task(node, upid):
        return {"status": "stopped", "exitstatus": "ERROR"}

    task_client.poll_task = stopped_task
    try:
        await task_client.wait_for_task("pve", "UPID:failed")
    except TaskError:
        pass
    else:
        raise AssertionError("failed Proxmox tasks must raise TaskError")

    print("Safety checks passed")


async def _safe_upgrade(client: FakeClient) -> dict:
    server = FastMCP(name="safety-test")
    register_dr_workflow_tools(server, client)
    tool = await server.get_tool("proxmox_dr_safe_upgrade")
    return await tool.fn(target_type="vm")


if __name__ == "__main__":
    asyncio.run(main())
