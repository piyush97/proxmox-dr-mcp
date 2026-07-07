# Proxmox DR Mnt": "# Proxmox DR MCP

**Automated disaster recovery for Proxmox VE** — pre-flight checks, smart snapshots, health verification, and rollback, all through natural language.

[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-Server-6366f1)](https://modelcontextprotocol.io)
[![MCPize](https://img.shields.io/badge/MCPize-Marketplace-22c55e)](https://mcpize.com/mcp/proxmox-dr-mcp)
[![GitHub Release](https://img.shields.io/github/v/release/piyush97/proxmox-dr-mcp)](https://github.com/piyush97/proxmox-dr-mcp/releases)

Give your AI assistant (Claude, Cursor, Codex, Windsurf) the ability to safely manage Proxmox disaster recovery — **one natural language command at a time**.

---

## ✨ Features

| Tool | Description |
|------|-------------|
| `proxmox_dr_preflight` | Check storage space, recent backups & running services before risky ops |
| `proxmox_dr_snapshot_create` | Create VM/LXC snapshots with auto-naming, descriptions & RAM state |
| `proxmox_dr_snapshot_list` | List all snapshots across the cluster with metadata |
| `proxmox_dr_snapshot_restore` | Rollback to a previous snapshot safely |
| `proxmox_dr_health_check` | Verify VMs/containers are running and healthy post-operation |
| `proxmox_dr_safe_upgrade` | **Orchestrated workflow**: preflight → snapshots → upgrade instructions → health check |

### Workflow: Safe Upgrade

The `proxmox_dr_safe_upgrade` tool runs a 4-step orchestrated workflow:

1. **Pre-flight** — checks storage space, backup freshness, running services
2. **Snapshot** — creates pre-upgrade snapshots of all targets
3. **Instructions** — tells you the upgrade is safe to proceed
4. **Health Check** — verifies everything is healthy after your maintenance

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- A Proxmox VE host with API token configured

### Installation

```bash
pip install proxmox-dr-mcp
```

Or run from source:

```bash
git clone https://github.com/piyush97/proxmox-dr-mcp.git
cd proxmox-dr-mcp
pip install -e .
```

### Configuration

Set these environment variables (or copy `.env.example` to `.env`):

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

---

## 🔌 Client Configuration

### Claude Desktop

Add to `claude_desktop_config.json`:

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

### Cursor / Windsurf / VS Code (Cline)

Add to your MCP settings file:

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

### Claude Code / Codex CLI

```bash
claude mcp add proxmox-dr -- pipx run proxmox-dr-mcp \
  --env PROXMOX_HOST=192.168.1.100 \
  --env PROXMOX_TOKEN_ID=my-token \
  --env PROXMOX_TOKEN_VALUE=my-secret
```

---

## 💬 Example Prompts

Once connected, try these:

| Prompt | What happens |
|--------|-------------|
| *"Run a pre-flight check before I upgrade my Proxmox host"* | Checks disk space, backups, running services |
| *"Create snapshots of all my VMs before the kernel update"* | Snapshots every VM with auto-naming |
| *"Run a safe upgrade workflow on VM 101"* | Full 4-step orchestrated workflow |
| *"List all recent snapshots"* | Shows snapshot inventory across the cluster |
| *"Check if all my containers are healthy"* | Health check on every LXC |
| *"Rollback VM 102 to the snapshot from yesterday"* | One-command rollback |

---

## 🏗 Project Structure

```
src/proxmox_dr_mcp/
├── __init__.py          # Package init
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

---

## 🧪 Development

```bash
# Clone and set up
git clone https://github.com/piyush97/proxmox-dr-mcp.git
cd proxmox-dr-mcp
uv sync

# Run smoke tests
uv run python tests/test_smoke.py

# Run live integration test (requires Proxmox env vars)
uv run python tests/test_live.py
```

---

## 📦 Deploy on MCPize

This server is available on the **MCPize marketplace**:

[**View on MCPize →**](https://mcpize.com/mcp/proxmox-dr-mcp)

Or deploy your own instance:

```bash
npx mcpize init my-server
npx mcpize deploy
```

---

## 📄 License

MIT — see [LICENSE](LICENSE)

## 👤 Author

[Piyush Mehta](https://github.com/piyush97) — Senior Software Engineer, AI/LLM/Agentic systems.
"}