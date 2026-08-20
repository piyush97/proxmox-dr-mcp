"""Pre-flight safety checks before risky operations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Literal

from fastmcp import FastMCP

from proxmox_dr_mcp.proxmox.client import ProxmoxClient
from proxmox_dr_mcp.utils.helpers import parse_vmid_list
from proxmox_dr_mcp.utils.types import PreflightReport

logger = logging.getLogger(__name__)


async def run_preflight(
    client: ProxmoxClient | None,
    target_type: Literal["vm", "lxc", "all"] = "all",
    target_ids: str = "all",
    storage_name: str | None = None,
) -> PreflightReport:
    """Return the shared read-only safety report used by DR tools."""
    warnings: list[str] = []
    if client is None:
        return PreflightReport(
            storage_free_gb={},
            has_recent_backups=False,
            running_services=[],
            warnings=["Proxmox credentials are not configured"],
            passed=False,
        )

    passed = True
    storage_free: dict[str, float] = {}
    nodes: list = []
    try:
        nodes = await client.get_nodes()
        for node_info in nodes:
            storages = await client.get_storage(node_info.node)
            for storage in storages:
                if storage_name and storage.storage != storage_name:
                    continue
                free_gb = round((storage.avail or 0) / (1024**3), 2)
                storage_free[f"{node_info.node}/{storage.storage}"] = free_gb
                if free_gb < 5:
                    warnings.append(
                        f"Low disk on {node_info.node}/{storage.storage}: {free_gb}GB free"
                    )
                    passed = False
    except Exception as exc:
        warnings.append(f"Failed to check storage: {exc}")
        passed = False

    has_recent = False
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).timestamp()
    try:
        for node_info in nodes:
            storages = await client.get_storage(node_info.node)
            for storage in storages:
                if "backup" not in storage.content.split(","):
                    continue
                content = await client.get_storage_content(node_info.node, storage.storage)
                has_recent = any(
                    "vzdump" in item.get("volid", "")
                    and isinstance(item.get("ctime"), (int, float))
                    and item["ctime"] >= cutoff
                    for item in content
                )
                if has_recent:
                    break
            if has_recent:
                break
    except Exception as exc:
        warnings.append(f"Failed to check backups: {exc}")

    if not has_recent:
        warnings.append("No backups found in last 7 days")
        passed = False

    running_list: list[dict] = []
    ids_filter = set(parse_vmid_list(target_ids)) if target_ids != "all" else None
    try:
        for node_info in nodes:
            if target_type in ("vm", "all"):
                for vm in await client.get_vms(node_info.node):
                    if vm.status == "running" and (ids_filter is None or vm.vmid in ids_filter):
                        running_list.append(
                            {"node": node_info.node, "vmid": vm.vmid, "type": "vm", "name": vm.name}
                        )
            if target_type in ("lxc", "all"):
                for ct in await client.get_containers(node_info.node):
                    if ct.status == "running" and (ids_filter is None or ct.vmid in ids_filter):
                        running_list.append(
                            {"node": node_info.node, "vmid": ct.vmid, "type": "lxc", "name": ct.name}
                        )
    except Exception as exc:
        warnings.append(f"Failed to check services: {exc}")
        passed = False

    return PreflightReport(
        storage_free_gb=storage_free,
        has_recent_backups=has_recent,
        running_services=running_list,
        warnings=warnings,
        passed=passed,
    )


def register_preflight_tools(server: FastMCP, client: ProxmoxClient) -> None:
    """Register pre-flight check MCP tools."""

    @server.tool(
        name="proxmox_dr_preflight",
        description="""Run pre-flight safety checks before risky operations.
        Checks: (1) available storage space, (2) whether recent backups exist,
        (3) current running services. Returns structured report with pass/fail.""",
    )
    async def proxmox_dr_preflight(
        target_type: Literal["vm", "lxc", "all"] = "all",
        target_ids: str = "all",
        storage_name: str | None = None,
    ) -> dict:
        """Run pre-flight checks.

        Args:
            target_type: "vm", "lxc", or "all"
            target_ids: Comma-separated IDs or "all"
            storage_name: Optional specific storage to check
        """
        return (
            await run_preflight(client, target_type, target_ids, storage_name)
        ).model_dump()
