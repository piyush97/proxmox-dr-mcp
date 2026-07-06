# Proxmox DR MCP

**Automated disaster recovery for Proxmox VE — pre-flight checks, smart snapshots, health verification, and rollback, all through natural language.**

[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)](pyproject.toml)

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that gives AI assistants (Claude, Cursor, Codex, etc.) the ability to safely manage Proxmox disaster recovery workflows.

## Features

| Tool | Description |
|------|-------------|
| `proxmox_dr_preflight` | Check storage space, recent backups, and running services before risky ops |
| `proxmox_dr_snapshot_create` | Create snapshots with auto-naming, descriptions, and RAM state |
| `proxmox_dr_snapshot_list` | List all snapshots across VMs/containers with metadata |
| `proxmox_dr_snapshot_restore` | Rollback to a previous snapshot |
| `proxmox_dr_health_check` | Verify services are healthy post-operation |
| `proxmox_dr_safe_upgrade` | **Orchestrated workflow**: preflight → snapshot → upgrade instructions → health check |

## Quick Start

### Prerequisites
- Python 3.10+
- A Proxmox VE host with API token configured

### Installation

```bash
pip install proxmox-dr-mcp
```

Or run from source:

```bash
git clone https://github.com/piyush97/proxmox-dr-mcp
cd proxmox-dr-mcp
pip install -e .
```

### Configuration

Set these environment variables (or create a `.env` file):

```env
PROXMOX_HOST=192.168.1.100
PROXMOX_TOKEN_ID=my-token-id
PROXMOX_TOKEN_VALUE=my-token-secret
PROXMOX_TOKEN_USER=root@pam
PROXMOX_VERIFY_SSL=false
NODE=pve
```

### Running

```bash
# Via pip entry point
proxmox-dr-mcp

# Or via Python module
python -m proxmox_dr_mcp
```

### Connecting to Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "proxmox-dr": {
      "command": "proxmox-dr-mcp",
      "env": {
        "PROXMOX_HOST": "192.168.1.100",
        "PROXMOX_TOKEN_ID": "my-token",
        "PROXMOX_TOKEN_VALUE": "my-secret"
      }
    }
  }
}
```

## Example Prompts

Once connected, try:

- *"Run a pre-flight check before I upgrade my Proxmox host"*
- *"Create snapshots of all my VMs before the kernel update"*
- *"Run a safe upgrade workflow on VM 101"*
- *"List all recent snapshots"*
- *"Check if all my containers are healthy"*
- *"Rollback VM 102 to the snapshot from yesterday"*

## Project Structure

```
src/proxmox_dr_mcp/
├── __init__.py
├── __main__.py          # Entry point
├── server.py            # FastMCP server + tool registration
├── config.py            # Pydantic-settings config
├── proxmox/
│   ├── client.py        # Async httpx Proxmox API client
│   ├── models.py        # Pydantic models for API responses
│   └── exceptions.py    # Custom exceptions
├── tools/
│   ├── preflight.py     # Pre-flight safety checks
│   ├── snapshot.py      # Snapshot CRUD
│   ├── health.py        # Health verification
│   └── dr_workflow.py   # Orchestrated DR workflow
└── utils/
    ├── types.py         # Shared MCP tool schemas
    ├── helpers.py       # Utility functions
    └── ssh.py           # SSH helpers
```

## License

MIT — see [LICENSE](LICENSE)

## Author

[Piyush Mehta](https://github.com/piyush97)
