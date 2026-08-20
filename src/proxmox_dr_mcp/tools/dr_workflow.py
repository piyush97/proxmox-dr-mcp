"""Orchestrated disaster recovery workflow tool."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from fastmcp import FastMCP

from proxmox_dr_mcp.config import get_config
from proxmox_dr_mcp.proxmox.client import ProxmoxClient
from proxmox_dr_mcp.tools.preflight import run_preflight
from proxmox_dr_mcp.utils.helpers import parse_vmid_list

logger = logging.getLogger(__name__)


def register_dr_workflow_tools(server: FastMCP, client: ProxmoxClient | None) -> None:
    """Register DR workflow MCP tools."""

    @server.tool(
        name="proxmox_dr_safe_upgrade",
        description="""Create verified pre-upgrade snapshots after a passing pre-flight check.
        Run proxmox_dr_health_check yourself after maintenance; this tool never claims
        post-upgrade health before the upgrade has happened.

        Pass preflight_only=True to only run the read-only safety check.""",
    )
    async def proxmox_dr_safe_upgrade(
        target_type: Literal["vm", "lxc", "all"] = "all",
        target_ids: str = "all",
        preflight_only: bool = False,
        snapshot_name: str | None = None,
    ) -> dict:
        """Run the preflight and snapshot phase of a safe upgrade."""
        workflow = {
            "workflow": "safe_upgrade",
            "target_type": target_type,
            "target_ids": target_ids if target_ids != "all" else "all targets",
            "steps": [],
            "success": False,
        }

        preflight = await run_preflight(client, target_type, target_ids)
        workflow["steps"].append(
            {"step": 1, "name": "preflight", "status": "complete", "result": preflight.model_dump()}
        )
        if not preflight.passed:
            workflow["summary"] = "Pre-flight did not pass; no snapshots were created."
            return workflow
        if preflight_only:
            workflow["success"] = True
            workflow["summary"] = "Pre-flight passed; no snapshots were created."
            return workflow
        if client is None:  # run_preflight already reports this; keeps the type boundary explicit.
            workflow["summary"] = "Proxmox credentials are not configured."
            return workflow

        ids_filter = set(parse_vmid_list(target_ids)) if target_ids != "all" else None
        targets: list[tuple[str, int, Literal["vm", "lxc"]]] = []
        try:
            for node_info in await client.get_nodes():
                if target_type in ("vm", "all"):
                    for vm in await client.get_vms(node_info.node):
                        if not vm.is_template and (ids_filter is None or vm.vmid in ids_filter):
                            targets.append((node_info.node, vm.vmid, "vm"))
                if target_type in ("lxc", "all"):
                    for ct in await client.get_containers(node_info.node):
                        if not ct.is_template and (ids_filter is None or ct.vmid in ids_filter):
                            targets.append((node_info.node, ct.vmid, "lxc"))
        except Exception as exc:
            workflow["steps"].append({"step": 2, "name": "snapshots", "status": "failed", "error": str(exc)})
            workflow["summary"] = f"Could not select snapshot targets: {exc}"
            return workflow

        if not targets:
            workflow["steps"].append({"step": 2, "name": "snapshots", "status": "failed", "error": "No targets matched"})
            workflow["summary"] = "No matching non-template targets; no snapshots were created."
            return workflow

        snapshot_name = snapshot_name or f"{get_config().default_snapshot_prefix}{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        snapshots: list[dict] = []
        errors: list[str] = []
        for node, vmid, actual_type in targets:
            try:
                upid = await client.create_snapshot(
                    node=node,
                    vmid=vmid,
                    snapname=snapshot_name,
                    description="Pre-upgrade snapshot via DR workflow",
                    target_type=actual_type,
                )
                await client.wait_for_task(node, upid, timeout=300)
                snapshots.append(
                    {"node": node, "vmid": vmid, "type": actual_type, "snapname": snapshot_name, "upid": upid}
                )
            except Exception as exc:
                logger.warning("Failed to snapshot %s/%s: %s", node, vmid, exc)
                errors.append(f"{node}/{vmid}: {exc}")

        if errors:
            workflow["steps"].append(
                {"step": 2, "name": "snapshots", "status": "failed", "snapshots": snapshots, "errors": errors}
            )
            workflow["summary"] = "Not every snapshot completed; do not proceed with maintenance."
            return workflow

        workflow["steps"].append(
            {"step": 2, "name": "snapshots", "status": "complete", "snapshot_name": snapshot_name, "snapshots": snapshots}
        )
        workflow["steps"].append(
            {
                "step": 3,
                "name": "instructions",
                "status": "ready",
                "message": "Snapshots completed. Perform maintenance, then run proxmox_dr_health_check.",
                "rollback_command": f"To rollback: proxmox_dr_snapshot_restore with snapname={snapshot_name}",
            }
        )
        workflow["success"] = True
        workflow["summary"] = f"{len(snapshots)} snapshots completed. Post-upgrade health has not been checked yet."
        return workflow
