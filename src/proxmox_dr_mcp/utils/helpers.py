"""Helper functions for Proxmox DR operations."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from proxmox_dr_mcp.proxmox.models import VMStatus, ContainerStatus

log = logging.getLogger(__name__)


def parse_vmid_list(vmid_str: str) -> list[int]:
    """Parse a VMID string into a list of integers.

    Accepts: "100,101,102" or "100-105" or "100"
    """
    if not vmid_str:
        return []
    result: set[int] = set()
    parts = [p.strip() for p in vmid_str.replace(" ", "").split(",")]
    for part in parts:
        if not part:
            continue
        range_match = re.match(r"^(\d+)-(\d+)$", part)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if start <= end:
                result.update(range(start, end + 1))
        else:
            try:
                result.add(int(part))
            except ValueError:
                log.warning("Invalid VMID: %s", part)
    return sorted(result)


def format_bytes(n: int | None) -> str:
    """Format bytes to human-readable string."""
    if n is None:
        return "N/A"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n //= 1024
    return f"{n:.1f} EiB"


def format_duration(seconds: int | None) -> str:
    """Format seconds to human-readable duration."""
    if seconds is None:
        return "N/A"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def timestamp_int(dt: datetime | None = None) -> int:
    """Get Unix timestamp from datetime or now."""
    dt = dt or utc_now()
    return int(dt.timestamp())


def vms_to_table(
    vms: list[VMStatus], headers: list[str] | None = None
) -> list[dict[str, Any]]:
    """Convert VM list to table rows for MCP tool output."""
    if headers is None:
        headers = ["VMID", "Name", "Status", "Node", "CPU", "Memory", "Disk"]
    rows = []
    for vm in vms:
        cpu_info = f"{vm.cpus}" if vm.cpus else "-"
        mem_str = format_bytes(vm.maxmem) if vm.maxmem else "-"
        disk_str = format_bytes(vm.maxdisk) if vm.maxdisk else "-"
        rows.append(
            {
                "vmid": str(vm.vmid),
                "name": vm.name,
                "status": vm.status,
                "node": vm.node,
                "cpus": cpu_info,
                "memory": mem_str,
                "disk": disk_str,
                "tags": vm.tags or "",
                "template": "yes" if vm.is_template else "no",
            }
        )
    return rows


def cts_to_table(cts: list[ContainerStatus]) -> list[dict[str, Any]]:
    """Convert container list to table rows."""
    rows = []
    for ct in cts:
        mem_str = format_bytes(ct.maxmem) if ct.maxmem else "-"
        disk_str = format_bytes(ct.maxdisk) if ct.maxdisk else "-"
        rows.append(
            {
                "vmid": str(ct.vmid),
                "name": ct.name,
                "status": ct.status,
                "node": ct.node,
                "cpus": str(ct.cpus) if ct.cpus else "-",
                "memory": mem_str,
                "disk": disk_str,
                "tags": ct.tags or "",
                "template": "yes" if ct.is_template else "no",
            }
        )
    return rows


def sanitize_name(name: str) -> str:
    """Sanitize a name string to be safe for Proxmox APIs."""
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name).strip("_.-") or "unnamed"