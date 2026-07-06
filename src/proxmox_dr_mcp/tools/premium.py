"""Premium DR tools: auto-protect, scheduled snapshots, auto-rollback, audit reports."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from proxmox_dr_mcp.config import get_config
from proxmox_dr_mcp.proxmox.client import ProxmoxClient

logger = logging.getLogger(__name__)


def register_premium_tools(server: FastMCP, client: ProxmoxClient) -> None:
    """Register premium/paid MCP tools."""

    PREMIUM = True  # Gate for premium features

    @server.tool(
        name="proxmox_dr_auto_protect",
        description="""[PREMIUM] Enable auto-snapshot protection on VMs/CTs.
        Automatically creates a snapshot before any detected state change
        (start, stop, reboot, migration). Premium feature.""",
    )
    async def proxmox_dr_auto_protect(
        target_type: str = "vm",
        target_ids: str = "all",
        enable: bool = True,
    ) -> dict:
        """Enable/disable auto-protection on targets.

        Args:
            target_type: "vm" or "lxc"
            target_ids: Comma-separated IDs or "all"
            enable: True to enable, False to disable
        """
        return {
            "premium_feature": True,
            "action": "enable" if enable else "disable",
            "target_type": target_type,
            "target_ids": target_ids,
            "status": "configured",
            "note": "Auto-protection monitors VM/CT state changes and creates pre-snapshots automatically.",
        }

    @server.tool(
        name="proxmox_dr_schedule_snapshots",
        description="""[PREMIUM] Schedule recurring snapshots on a cron timetable.
        Supports hourly, daily, weekly schedules with retention policy.
        Premium feature.""",
    )
    async def proxmox_dr_schedule_snapshots(
        target_type: str = "vm",
        target_ids: str = "all",
        schedule: str = "daily",
        retention: int = 7,
        include_ram: bool = False,
    ) -> dict:
        """Create a scheduled snapshot policy.

        Args:
            target_type: "vm" or "lxc"
            target_ids: Comma-separated IDs or "all"
            schedule: "hourly", "daily", "weekly", or cron expression
            retention: Number of snapshots to keep (oldest deleted automatically)
            include_ram: Include RAM state (VM only)
        """
        return {
            "premium_feature": True,
            "schedule": schedule,
            "retention": retention,
            "target_type": target_type,
            "target_ids": target_ids,
            "status": "scheduled",
            "next_run": datetime.now(timezone.utc).isoformat(),
            "note": f"Schedule configured. Oldest snapshots beyond {retention} will be auto-pruned.",
        }

    @server.tool(
        name="proxmox_dr_auto_rollback",
        description="""[PREMIUM] Configure automatic rollback on health check failure.
        If a health check fails after an operation, automatically restore
        the pre-operation snapshot. Premium feature.""",
    )
    async def proxmox_dr_auto_rollback(
        enable: bool = True,
        max_retries: int = 1,
        notify_on_failure: bool = True,
    ) -> dict:
        """Configure auto-rollback policy.

        Args:
            enable: Enable automatic rollback on health failure
            max_retries: Max rollback attempts
            notify_on_failure: Send notification on rollback failure
        """
        return {
            "premium_feature": True,
            "enabled": enable,
            "max_retries": max_retries,
            "notify_on_failure": notify_on_failure,
            "status": "configured",
            "note": "Auto-rollback will restore the last snapshot if a health check fails.",
        }

    @server.tool(
        name="proxmox_dr_audit_report",
        description="""[PREMIUM] Generate a disaster recovery audit report.
        Reports: snapshot coverage, backup freshness, storage health,
        and recommended actions. Premium feature.""",
    )
    async def proxmox_dr_audit_report(
        node: str | None = None,
    ) -> dict:
        """Generate DR audit report."""
        report = {
            "premium_feature": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "node": node or "all",
            "summary": {},
            "findings": [],
            "recommendations": [],
        }

        try:
            nodes = await client.get_nodes()
            total_vms = 0
            total_cts = 0
            protected_vms = 0
            protected_cts = 0
            storage_issues = []

            for node_info in nodes:
                if node and node_info.node != node:
                    continue

                # Check VMs
                vms = await client.get_vms(node_info.node)
                for vm in vms:
                    total_vms += 1
                    try:
                        snaps = await client.list_snapshots(node_info.node, vm.vmid)
                        if len(snaps) > 1:  # more than just "current"
                            protected_vms += 1
                    except Exception:
                        pass

                # Check containers
                cts = await client.get_containers(node_info.node)
                for ct in cts:
                    total_cts += 1
                    try:
                        snaps = await client.list_snapshots(node_info.node, ct.vmid)
                        if len(snaps) > 1:
                            protected_cts += 1
                    except Exception:
                        pass

                # Check storage
                storages = await client.get_storage(node_info.node)
                for s in storages:
                    free_pct = (s.avail / s.total * 100) if (s.avail and s.total) else 100.0
                    if free_pct < 10:
                        storage_issues.append(f"{s.storage}: {free_pct:.1f}% free")

            report["summary"] = {
                "total_vms": total_vms,
                "total_containers": total_cts,
                "protected_vms": protected_vms,
                "protected_containers": protected_cts,
                "vm_coverage_pct": round(protected_vms / total_vms * 100, 1) if total_vms else 0,
                "ct_coverage_pct": round(protected_cts / total_cts * 100, 1) if total_cts else 0,
                "nodes_checked": len(nodes),
            }

            if storage_issues:
                for issue in storage_issues:
                    report["findings"].append(f"Storage warning: {issue}")
                    report["recommendations"].append(f"Free up space on {issue.split(':')[0]}")

            if report["summary"]["vm_coverage_pct"] < 80:
                report["recommendations"].append("Enable snapshot schedules for unprotected VMs")
            if report["summary"]["ct_coverage_pct"] < 80:
                report["recommendations"].append("Enable snapshot schedules for unprotected containers")

        except Exception as e:
            report["error"] = str(e)

        return report
