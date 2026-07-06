"""Pydantic models for Proxmox VE entities."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Nodes ────────────────────────────────────────────────────────────────────


class Node(BaseModel):
    """A Proxmox VE cluster node."""

    node: str
    status: Literal["online", "offline", "unknown"]
    cpu: float | None = None
    maxcpu: int | None = None
    mem: int | None = None
    maxmem: int | None = None
    disk: int | None = None
    maxdisk: int | None = None
    uptime: int | None = None
    id: str | None = None
    level: str | None = None

    @property
    def cpu_usage_pct(self) -> float | None:
        if self.maxcpu and self.maxcpu > 0:
            return round(((self.cpu or 0) / self.maxcpu) * 100, 1)
        return None

    @property
    def mem_usage_pct(self) -> float | None:
        if self.maxmem and self.maxmem > 0:
            return round(((self.mem or 0) / self.maxmem) * 100, 1)
        return None


# ── VMs & Containers ─────────────────────────────────────────────────────────


class VMStatus(BaseModel):
    """A QEMU virtual machine."""

    vmid: int
    name: str
    status: Literal["running", "stopped", "paused"]
    node: str
    mem: int | None = None
    maxmem: int | None = None
    cpus: int | None = None
    uptime: int | None = None
    disk: int | None = None
    maxdisk: int | None = None
    tags: str | None = None
    template: int = 0

    @property
    def is_template(self) -> bool:
        return self.template == 1


class ContainerStatus(BaseModel):
    """An LXC container."""

    vmid: int
    name: str
    status: Literal["running", "stopped"]
    node: str
    mem: int | None = None
    maxmem: int | None = None
    cpus: int | None = None
    uptime: int | None = None
    disk: int | None = None
    maxdisk: int | None = None
    swap: int | None = None
    maxswap: int | None = None
    tags: str | None = None
    template: int = 0

    @property
    def is_template(self) -> bool:
        return self.template == 1


# ── Snapshots ────────────────────────────────────────────────────────────────


class Snapshot(BaseModel):
    """A VM/CT snapshot."""

    name: str
    description: str | None = None
    snapstate: str | None = None
    snaptime: int | None = None
    parent: str | None = None
    vmid: int
    node: str
    ram: bool | None = None
    running: bool | None = None

    @property
    def created(self) -> datetime | None:
        if self.snaptime:
            return datetime.fromtimestamp(self.snaptime)
        return None


# ── Backups ──────────────────────────────────────────────────────────────────


class BackupJob(BaseModel):
    """A backup job definition."""

    id: str
    vmid: str | None = None
    node: str | None = None
    storage: str
    mode: Literal["snapshot", "suspend", "stop"] = "snapshot"
    schedule: str | None = None
    enabled: bool = True
    compress: str | None = None
    bwlimit: int | None = None
    all: bool = False
    exclude: str | None = None
    mailnotification: str | None = None
    notes: str | None = None
    performance: str | None = None
    repeat_missed: bool | None = None
    protected: bool = False


class BackupInfo(BaseModel):
    """A single backup archive on storage."""

    volid: str
    size: int
    vmid: int
    content: str = "backup"
    format: str | None = None
    notes: str | None = None
    ctime: int | None = None
    type: Literal["qemu", "lxc"] | None = None

    @property
    def created(self) -> datetime | None:
        if self.ctime:
            return datetime.fromtimestamp(self.ctime)
        return None


# ── Replication ──────────────────────────────────────────────────────────────


class ReplicationJob(BaseModel):
    """A replication job configuration."""

    id: str
    node: str | None = None
    target: str | None = None
    type: str = "local"
    schedule: str | None = None
    rate: int | None = None
    comment: str | None = None
    enabled: bool = True
    job_id: str | None = None


# ── Storage ──────────────────────────────────────────────────────────────────


class Storage(BaseModel):
    """A Proxmox storage definition."""

    storage: str
    type: str
    content: str
    active: bool = False
    enabled: bool = True
    used_fraction: float | None = None
    total: int | None = None
    used: int | None = None
    avail: int | None = None
    node: str | None = None


# ── Cluster ──────────────────────────────────────────────────────────────────


class ClusterStatus(BaseModel):
    """Cluster status information."""

    name: str | None = None
    quorate: bool | None = None
    quorum: int | None = None
    nodes: list[Node] = Field(default_factory=list)
    version: int | None = None


class ClusterResource(BaseModel):
    """A cluster-wide resource."""

    id: str
    type: str
    node: str | None = None
    status: str | None = None
    vmid: int | None = None
    name: str | None = None
    level: str | None = None


# ── Tasks ────────────────────────────────────────────────────────────────────


class TaskStatus(BaseModel):
    """Status of a Proxmox task."""

    upid: str
    status: Literal["running", "stopped", "error", "unknown"] = "unknown"
    exitstatus: str | None = None
    starttime: int | None = None
    endtime: int | None = None
    node: str
    pid: int | None = None
    pstart: int | None = None
    type: str | None = None
    user: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status == "stopped" and self.exitstatus == "OK"

    @property
    def is_error(self) -> bool:
        return self.status in ("error",) or (
            self.status == "stopped" and self.exitstatus and self.exitstatus != "OK"
        )

    @property
    def duration_seconds(self) -> int | None:
        if self.starttime and self.endtime:
            return self.endtime - self.starttime
        return None


# ── Network ──────────────────────────────────────────────────────────────────


class FirewallRule(BaseModel):
    """A firewall rule."""

    pos: int | None = None
    type: Literal["in", "out"] = "in"
    action: Literal["ACCEPT", "DROP", "REJECT"] = "ACCEPT"
    enable: bool = True
    comment: str | None = None
    iface: str | None = None
    proto: str | None = None
    source: str | None = None
    dest: str | None = None
    dport: str | None = None
    sport: str | None = None
    log: str | None = None


# ── DR-specific ──────────────────────────────────────────────────────────────


class DRPlan(BaseModel):
    """A disaster recovery plan for a set of VMs/CTs."""

    name: str
    vmid_list: list[int]
    target_node: str | None = None
    target_storage: str | None = None
    pre_restore_commands: list[str] = Field(default_factory=list)
    post_restore_commands: list[str] = Field(default_factory=list)
    start_vms_after_restore: bool = True
    restore_timeout_seconds: int = 300


class DRRestoreResult(BaseModel):
    """Result of a DR restore operation."""

    vmid: int
    name: str | None = None
    success: bool
    backup_volid: str | None = None
    task_upid: str | None = None
    error: str | None = None
    duration_seconds: float | None = None


class DRBackupResult(BaseModel):
    """Result of a DR backup operation."""

    vmid: int
    name: str | None = None
    success: bool
    task_upid: str | None = None
    backup_volid: str | None = None
    error: str | None = None
    duration_seconds: float | None = None
    snapshot_name: str | None = None


class DRHealthStatus(BaseModel):
    """Overall DR health snapshot."""

    cluster_quorate: bool | None = None
    nodes_online: int = 0
    nodes_total: int = 0
    vms_protected: int = 0
    vms_total: int = 0
    ct_protected: int = 0
    ct_total: int = 0
    latest_backup_timestamp: datetime | None = None
    replication_lag_seconds: int | None = None
    last_health_check: datetime | None = None
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SyncOperation(BaseModel):
    """Result of a configuration sync operation."""

    source_host: str
    target_host: str
    synced_at: datetime
    entries_synced: int = 0
    errors: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)