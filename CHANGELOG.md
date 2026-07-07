# Changelog

## v0.1.0 (2026-07-06)

Initial public release of Proxmox DR MCP — automated disaster recovery for Proxmox VE.

### Added
- `proxmox_dr_preflight` — storage space, backup freshness & running service checks
- `proxmox_dr_snapshot_create` — create VM/LXC snapshots with auto-naming
- `proxmox_dr_snapshot_list` — list all snapshots across the cluster
- `proxmox_dr_snapshot_restore` — rollback VMs/containers to previous snapshots
- `proxmox_dr_health_check` — verify services are running post-operation
- `proxmox_dr_safe_upgrade` — orchestrated 4-step workflow (preflight → snapshot → upgrade → health check)
- HTTP transport with FastMCP for MCPize deployment
- Health endpoint for platform checks
- Task polling for atomic snapshot operations
- Dockerfile for containerized deployment
- MCPize marketplace listing

### Fixed
- Container PermissionError: `chmod -R o+r` for `nobody` user
- Config crash on boot: made Proxmox credentials optional
- Deferred config validation to tool execution time
