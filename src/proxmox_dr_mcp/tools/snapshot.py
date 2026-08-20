"""Snapshot management tools — create, list, rollback."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from fastmcp import FastMCP

from proxmox_dr_mcp.config import get_config
from proxmox_dr_mcp.proxmox.client import ProxmoxClient
from proxmox_dr_mcp.utils.helpers import parse_vmid_list
from proxmox_dr_mcp.utils.types import SnapshotInfo

logger = logging.getLogger(__name__)


def register_snapshot_tools(server: FastMCP, client: ProxmoxClient | None) -> None:
    """Register snapshot management MCP tools."""
    config = get_config()

    @server.tool(
        name="proxmox_dr_snapshot_create",
        description="""Create snapshots for one or more VMs/containers.
        Auto-generates name if not provided. Optionally include RAM state.""",
    )
    async def proxmox_dr_snapshot_create(
        target_type: Literal["vm", "lxc", "all"] = "vm",
        target_ids: str = "all",
        name: str | None = None,
        description: str = "",
        include_ram: bool = False,
    ) -> dict:
        """Create snapshots.

        Args:
            target_type: "vm" or "lxc"
            target_ids: Comma-separated IDs or "all"
            name: Snapshot name (auto-generated if None)
            description: Optional description
            include_ram: Include RAM state (VM only, requires VM to be running)
        """
        if not name:
            name = f"{config.default_snapshot_prefix}{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        results: list[dict] = []
        errors: list[str] = []
        ids_filter = set(parse_vmid_list(target_ids)) if target_ids != "all" else None

        if client is None:
            return {"snapshots": [], "errors": ["Proxmox credentials are not configured"], "total": 0, "failed": 1}

        try:
            nodes = await client.get_nodes()
            for node_info in nodes:
                items = []
                if target_type in ("vm", "all"):
                    vms = await client.get_vms(node_info.node)
                    for vm in vms:
                        if ids_filter is not None and vm.vmid not in ids_filter:
                            continue
                        if vm.is_template:
                            continue
                        items.append((node_info.node, vm.vmid, "vm"))
                if target_type in ("lxc", "all"):
                    cts = await client.get_containers(node_info.node)
                    for ct in cts:
                        if ids_filter is not None and ct.vmid not in ids_filter:
                            continue
                        if ct.is_template:
                            continue
                        items.append((node_info.node, ct.vmid, "lxc"))

                for node, vmid, actual_type in items:
                    try:
                        upid = await client.create_snapshot(
                            node=node,
                            vmid=vmid,
                            snapname=name,
                            description=description,
                            vmstate=include_ram and actual_type == "vm",
                            target_type=actual_type,
                        )
                        results.append({
                            "node": node,
                            "vmid": vmid,
                            "type": actual_type,
                            "snapname": name,
                            "upid": upid,
                            "status": "requested",
                        })
                    except Exception as e:
                        errors.append(f"{node}/{vmid}: {e}")
        except Exception as e:
            errors.append(f"Failed to list nodes: {e}")

        if not results and not errors:
            errors.append("No matching non-template targets")

        return {
            "snapshots": results,
            "errors": errors,
            "total": len(results),
            "failed": len(errors),
        }

    @server.tool(
        name="proxmox_dr_snapshot_list",
        description="List all snapshots for VMs/containers across the cluster.",
    )
    async def proxmox_dr_snapshot_list(
        target_type: Literal["vm", "lxc", "all"] = "all",
        target_id: int | None = None,
        node: str | None = None,
    ) -> list[dict]:
        """List snapshots."""
        snapshots: list[SnapshotInfo] = []

        if client is None:
            logger.error("Proxmox credentials are not configured")
            return []

        try:
            nodes = await client.get_nodes()
            for node_info in nodes:
                if node and node_info.node != node:
                    continue
                items = []
                if target_type in ("vm", "all"):
                    vms = await client.get_vms(node_info.node)
                    for vm in vms:
                        if target_id and vm.vmid != target_id:
                            continue
                        items.append((node_info.node, vm.vmid, "vm"))
                if target_type in ("lxc", "all"):
                    cts = await client.get_containers(node_info.node)
                    for ct in cts:
                        if target_id and ct.vmid != target_id:
                            continue
                        items.append((node_info.node, ct.vmid, "lxc"))

                for n, vmid, atype in items:
                    try:
                        snaps = await client.list_snapshots(n, vmid, target_type=atype)
                        for s in snaps:
                            if s.name == "current":
                                continue
                            snapshots.append(SnapshotInfo(
                                node=n,
                                vmid=vmid,
                                snapname=s.name,
                                description=s.description or "",
                                snaptime_iso=s.created.isoformat() if s.created else "",
                                vmstate=s.ram or False,
                                target_type=atype,
                            ))
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Failed to list snapshots: {e}")

        return [s.model_dump() for s in snapshots]

    @server.tool(
        name="proxmox_dr_snapshot_restore",
        description="""Rollback a VM/container to a previous snapshot.
        WARNING: This will stop the VM/CT and restore to snapshot state.""",
    )
    async def proxmox_dr_snapshot_restore(
        node: str,
        vmid: int,
        snapname: str,
        target_type: Literal["vm", "lxc"] = "vm",
    ) -> dict:
        """Restore a snapshot.

        Args:
            node: Proxmox node name
            vmid: VM or container ID
            snapname: Snapshot name to restore
            target_type: "vm" or "lxc"
        """
        if client is None:
            return {"success": False, "node": node, "vmid": vmid, "snapname": snapname, "error": "Proxmox credentials are not configured"}

        try:
            upid = await client.rollback_snapshot(
                node=node,
                vmid=vmid,
                snapname=snapname,
                target_type=target_type,
            )
            return {
                "success": True,
                "node": node,
                "vmid": vmid,
                "snapname": snapname,
                "upid": upid,
                "message": f"Rollback to {snapname} initiated on {node}/{vmid}",
            }
        except Exception as e:
            return {
                "success": False,
                "node": node,
                "vmid": vmid,
                "snapname": snapname,
                "error": str(e),
            }
