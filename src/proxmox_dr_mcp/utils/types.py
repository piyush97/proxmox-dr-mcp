"""Shared Pydantic models and type definitions for MCP tool parameters."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TargetType = Literal["vm", "lxc"]


class PreflightTarget(BaseModel):
    target_type: TargetType
    target_ids: list[int] | Literal["all"] = Field(default="all")
    storage_name: str | None = Field(default=None, description="Optional specific storage to check")


class SnapshotCreateParams(BaseModel):
    target_type: TargetType
    target_ids: list[int] | Literal["all"] = Field(default="all")
    name: str | None = Field(default=None, description="Auto-generated if empty")
    description: str = Field(default="")
    include_ram: bool = Field(default=False, description="Include RAM state (VM only)")


class SnapshotRestoreParams(BaseModel):
    node: str
    vmid: int
    snapname: str
    target_type: TargetType


class HealthCheckTarget(BaseModel):
    node: str
    vmid: int
    target_type: TargetType


class SafeUpgradeParams(BaseModel):
    target_type: TargetType
    target_ids: list[int] | Literal["all"] = Field(default="all")
    preflight_only: bool = Field(default=False, description="Only run preflight, don't take action")
    skip_health_check: bool = Field(default=False)


class PreflightReport(BaseModel):
    storage_free_gb: dict[str, float] = Field(description="GB free per storage pool")
    has_recent_backups: bool = Field(description="Any backup in last 7 days")
    running_services: list[dict] = Field(description="Running VMs/CTs")
    warnings: list[str] = Field(default_factory=list)
    passed: bool = Field(description="True if all checks pass")


class SnapshotInfo(BaseModel):
    node: str
    vmid: int
    snapname: str
    description: str = ""
    snaptime_iso: str = ""
    vmstate: bool = False
    target_type: TargetType = "vm"


class HealthCheckResult(BaseModel):
    node: str
    vmid: int
    target_type: TargetType
    status: Literal["running", "stopped", "paused", "unknown"]
    passed: bool
    details: str = ""


class DrWorkflowResult(BaseModel):
    preflight: PreflightReport | None
    snapshots_created: list[SnapshotInfo] = Field(default_factory=list)
    health_checks: list[HealthCheckResult] = Field(default_factory=list)
    rollback_performed: bool = False
    success: bool = True
    summary: str = ""
