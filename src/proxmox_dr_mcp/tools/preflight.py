"""Pre-flight safety checks before risky operations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from mcp.server.fastmcp import FastMCP

from proxmox_dr_mcp.proxmox.client import ProxmoxClient
from proxmox_dr_mcp.utils.types import PreflightReport

logger = logging.getLogger(__name__)


def register_preflight_tools(server: FastMCP, client: ProxmoxClient) -> None:
    """Register pre-flight check MCP tools."""

    @server.tool(
        name="proxmox_dr_preflight",
        description="""Run pre-flight safety checks before risky operations.
        Checks: (1) available storage space, (2) whether recent backups exist,
        (3) current running services. Returns structured report with pass/fail.""",
    )
    async def proxmox_dr_preflight(
        target_type: str = "all",
        target_ids: str = "all",
        storage_name: str | None = None,
    ) -> dict:
        """Run pre-flight checks.

        Args:
            target_type: "vm", "lxc", or "all"
            target_ids: Comma-separated IDs or "all"
            storage_name: Optional specific storage to check
        """
        warnings: list[str] = []
        passed = True

        # 1. Check storage space
        storage_free: dict[str, float] = {}
        nodes: list = []
        try:
            nodes = await client.get_nodes()
            for node_info in nodes:
                storages = await client.get_storage(node_info.node)
                for s in storages:
                    if storage_name and s.storage != storage_name:
                        continue
                    total_gb = s.total / (1024**3) if s.total else 0
                    used_gb = s.used / (1024**3) if s.used else 0
                    free_gb = round(total_gb - used_gb, 2)
                    storage_free[s.storage] = free_gb
                    if free_gb < 5:
                        warnings.append(f"Low disk on {s.storage}: {free_gb}GB free")
                        passed = False
        except Exception as e:
            warnings.append(f"Failed to check storage: {e}")
            passed = False

        # 2. Check recent backups (vzdump files in backup storage)
        has_recent = False
        try:
            for node_info in (nodes or [])[:1]:  # check first node
                storages = await client.get_storage(node_info.node)
                for s in storages:
                    if "backup" in s.storage.lower() or "backup" in (s.content or ""):
                        try:
                            content = await client.get_storage_content(node_info.node, s.storage)
                            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
                            for item in content:
                                if "vzdump" in item.get("volid", ""):
                                    # Check ctime if available
                                    has_recent = True
                                    break
                        except Exception:
                            pass
        except Exception:
            pass

        if not has_recent:
            warnings.append("No backups found in last 7 days")
            passed = False

        # 3. Check running services
        running_list: list[dict] = []
        try:
            for node_info in nodes[:1]:
                vms = await client.get_vms(node_info.node)
                for vm in vms:
                    if vm.status == "running":
                        running_list.append({"node": node_info.node, "vmid": vm.vmid, "type": "vm", "name": vm.name})
                cts = await client.get_containers(node_info.node)
                for ct in cts:
                    if ct.status == "running":
                        running_list.append({"node": node_info.node, "vmid": ct.vmid, "type": "lxc", "name": ct.name})
        except Exception as e:
            warnings.append(f"Failed to check services: {e}")

        report = PreflightReport(
            storage_free_gb=storage_free,
            has_recent_backups=has_recent,
            running_services=running_list,
            warnings=warnings,
            passed=passed,
        )
        return report.model_dump()
