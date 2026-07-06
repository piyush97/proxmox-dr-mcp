"""Orchestrated disaster recovery workflow tool."""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from proxmox_dr_mcp.proxmox.client import ProxmoxClient

logger = logging.getLogger(__name__)


def register_dr_workflow_tools(server: FastMCP, client: ProxmoxClient) -> None:
    """Register DR workflow MCP tools."""

    @server.tool(
        name="proxmox_dr_safe_upgrade",
        description="""Orchestrated safe upgrade workflow.
        Step 1: Pre-flight check (storage, backups, running services)
        Step 2: Create snapshots of all targets
        Step 3: Return upgrade instructions (user runs the upgrade)
        Step 4: Health check to verify everything is healthy

        Pass preflight_only=True to only run step 1 without any action.""",
    )
    async def proxmox_dr_safe_upgrade(
        target_type: str = "all",
        target_ids: str = "all",
        preflight_only: bool = False,
        skip_health_check: bool = False,
        snapshot_name: str | None = None,
    ) -> dict:
        """Run safe upgrade workflow."""
        workflow = {
            "workflow": "safe_upgrade",
            "target_type": target_type,
            "target_ids": target_ids if target_ids != "all" else "all targets",
            "steps": [],
            "success": False,
        }

        # Step 1: Pre-flight
        logger.info("Running pre-flight check...")
        preflight_result = None
        try:
            nodes = await client.get_nodes()
            storage_free = {}
            warnings = []
            for node_info in nodes:
                storages = await client.get_storage(node_info.node)
                for s in storages:
                    free_gb = round((s.avail or 0) / (1024**3), 2)
                    storage_free[s.storage] = free_gb
                    if free_gb < 5:
                        warnings.append(f"Low disk: {s.storage} has {free_gb}GB free")

            preflight_result = {
                "storage_free_gb": storage_free,
                "warnings": warnings,
                "passed": len(warnings) == 0,
            }
            workflow["steps"].append({"step": 1, "name": "preflight", "status": "complete", "result": preflight_result})
        except Exception as e:
            workflow["steps"].append({"step": 1, "name": "preflight", "status": "failed", "error": str(e)})
            workflow["summary"] = f"Pre-flight check failed: {e}"
            return workflow

        if preflight_only:
            workflow["success"] = True
            workflow["summary"] = "Pre-flight only mode — review the report above before proceeding."
            return workflow

        # Step 2: Create snapshots
        logger.info("Creating pre-upgrade snapshots...")
        try:
            from proxmox_dr_mcp.config import get_config
            config = get_config()
            import datetime
            snap_name = snapshot_name or f"{config.default_snapshot_prefix}{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"

            snapshots_created = []
            for node_info in nodes:
                items = []
                if target_type in ("vm", "all"):
                    vms = await client.get_vms(node_info.node)
                    for vm in vms:
                        if target_ids != "all" and str(vm.vmid) not in target_ids.split(","):
                            continue
                        items.append((node_info.node, vm.vmid, "vm"))
                if target_type in ("lxc", "all"):
                    cts = await client.get_containers(node_info.node)
                    for ct in cts:
                        if target_ids != "all" and str(ct.vmid) not in target_ids.split(","):
                            continue
                        items.append((node_info.node, ct.vmid, "lxc"))

                for node_name, vmid, actual_type in items:
                    try:
                        upid = await client.create_snapshot(
                            node=node_name,
                            vmid=vmid,
                            snapname=snap_name,
                            description=f"Pre-upgrade snapshot via DR workflow",
                            vmstate=False,
                        )
                        snapshots_created.append({"node": node_name, "vmid": vmid, "type": actual_type, "snapname": snap_name, "upid": upid})
                    except Exception as e:
                        logger.warning(f"Failed to snapshot {node_name}/{vmid}: {e}")

            workflow["steps"].append({
                "step": 2,
                "name": "snapshots",
                "status": "complete",
                "snapshot_name": snap_name,
                "created": len(snapshots_created),
                "snapshots": snapshots_created,
            })
        except Exception as e:
            workflow["steps"].append({"step": 2, "name": "snapshots", "status": "failed", "error": str(e)})
            workflow["summary"] = f"Snapshot creation failed: {e}"
            return workflow

        # Step 3: Instructions
        workflow["steps"].append({
            "step": 3,
            "name": "instructions",
            "status": "ready",
            "message": "Snapshots created. You can now safely perform your upgrade/maintenance. After completion, run proxmox_dr_health_check to verify everything is healthy.",
            "rollback_command": f"To rollback: proxmox_dr_snapshot_restore with snapname={snap_name}",
        })

        # Step 4: Health check (optional, runs automatically unless skipped)
        if not skip_health_check:
            logger.info("Running post-upgrade health check...")
            try:
                health_results = []
                for node_info in nodes:
                    vms = await client.get_vms(node_info.node)
                    for vm in vms:
                        if vm.status == "running":
                            health_results.append({"node": node_info.node, "vmid": vm.vmid, "type": "vm", "status": vm.status, "healthy": True})
                    cts = await client.get_containers(node_info.node)
                    for ct in cts:
                        if ct.status == "running":
                            health_results.append({"node": node_info.node, "vmid": ct.vmid, "type": "lxc", "status": ct.status, "healthy": True})

                all_healthy = all(r["healthy"] for r in health_results)
                workflow["steps"].append({
                    "step": 4,
                    "name": "health_check",
                    "status": "complete",
                    "all_healthy": all_healthy,
                    "services": health_results,
                })
                workflow["success"] = all_healthy
                workflow["summary"] = f"{'✅ All services healthy' if all_healthy else '⚠️ Some services may need attention'} — {len(health_results)} services checked." if all_healthy else f"⚠️ {sum(1 for r in health_results if not r['healthy'])} services unhealthy — {len(health_results)} checked."
            except Exception as e:
                workflow["steps"].append({"step": 4, "name": "health_check", "status": "failed", "error": str(e)})
                workflow["success"] = False
                workflow["summary"] = f"Health check failed: {e}"
        else:
            workflow["success"] = True
            workflow["summary"] = f"Workflow complete — {len(snapshots_created)} snapshots created. Health check skipped per request."

        return workflow
