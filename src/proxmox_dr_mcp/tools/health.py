"""Post-operation health verification tools."""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from proxmox_dr_mcp.proxmox.client import ProxmoxClient
from proxmox_dr_mcp.utils.types import HealthCheckResult

logger = logging.getLogger(__name__)


def register_health_tools(server: FastMCP, client: ProxmoxClient) -> None:
    """Register health check MCP tools."""

    @server.tool(
        name="proxmox_dr_health_check",
        description="""Verify VMs/containers are healthy after an operation.
        Checks: status is 'running', basic resource usage is normal.""",
    )
    async def proxmox_dr_health_check(
        targets: list[dict] | None = None,
        target_type: str = "all",
        target_ids: str = "all",
    ) -> dict:
        """Run health checks.

        Args:
            targets: Explicit list of {node, vmid, target_type} to check
            target_type: "vm", "lxc", or "all" (used if targets not provided)
            target_ids: Comma-separated IDs or "all" (used if targets not provided)
        Returns:
            Dict with results per target and overall pass/fail
        """
        results: list[HealthCheckResult] = []

        try:
            nodes = await client.get_nodes()

            if targets:
                # Check specific targets
                for t in targets:
                    node_name = t.get("node", "")
                    vmid = t.get("vmid", 0)
                    ttype = t.get("target_type", "vm")
                    try:
                        if ttype == "vm":
                            status = await client.get_vm_status(node_name, vmid)
                            passed = status.status == "running"
                            results.append(HealthCheckResult(
                                node=node_name,
                                vmid=vmid,
                                target_type=ttype,
                                status=status.status,
                                passed=passed,
                                details=f"Status: {status.status}",
                            ))
                        else:
                            status = await client.get_ct_status(node_name, vmid)
                            passed = status.status == "running"
                            results.append(HealthCheckResult(
                                node=node_name,
                                vmid=vmid,
                                target_type=ttype,
                                status=status.status,
                                passed=passed,
                                details=f"Status: {status.status}",
                            ))
                    except Exception as e:
                        results.append(HealthCheckResult(
                            node=node_name,
                            vmid=vmid,
                            target_type=ttype,
                            status="unknown",
                            passed=False,
                            details=f"Error: {e}",
                        ))
            else:
                # Check all matching
                ids_filter = target_ids.split(",") if target_ids != "all" else None
                for node_info in nodes[:1]:
                    if target_type in ("vm", "all"):
                        vms = await client.get_vms(node_info.node)
                        for vm in vms:
                            if ids_filter and str(vm.vmid) not in ids_filter:
                                continue
                            passed = vm.status == "running"
                            results.append(HealthCheckResult(
                                node=node_info.node,
                                vmid=vm.vmid,
                                target_type="vm",
                                status=vm.status,
                                passed=passed,
                                details=f"Status: {vm.status}, CPU: {vm.cpus or '?'} cores",
                            ))
                    if target_type in ("lxc", "all"):
                        cts = await client.get_containers(node_info.node)
                        for ct in cts:
                            if ids_filter and str(ct.vmid) not in ids_filter:
                                continue
                            passed = ct.status == "running"
                            results.append(HealthCheckResult(
                                node=node_info.node,
                                vmid=ct.vmid,
                                target_type="lxc",
                                status=ct.status,
                                passed=passed,
                                details=f"Status: {ct.status}, RAM: {ct.mem or 0} bytes",
                            ))
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return {"error": str(e), "results": [], "all_passed": False}

        all_passed = all(r.passed for r in results)
        return {
            "results": [r.model_dump() for r in results],
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "all_passed": all_passed,
        }
