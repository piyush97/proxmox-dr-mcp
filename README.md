# Proxmox DR MCP

**Automated disaster recovery for Proxmox VE** — pre-flight checks, smart snapshots, health verification, and rollback, all through natural language.

[![CI](https://github.com/piyush97/proxmox-dr-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/piyush97/proxmox-dr-mcp/actions/workflows/ci.yml)
[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-Server-6366f1)](https://modelcontextprotocol.io)
[![MCPize](https://img.shields.io/badge/MCPize-Marketplace-22c55e)](https://mcpize.com/mcp/proxmox-dr-mcp)
[![GitHub Release](https://img.shields.io/github/v/release/piyush97/proxmox-dr-mcp)](https://github.com/piyush97/proxmox-dr-mcp/releases)

Give your AI assistant (Claude, Cursor, Codex, Windsurf) the ability to safely manage Proxmox disaster recovery — **one natural language command at a time**.

---

## 🏗 Architecture

The server is a [FastMCP](https://modelcontextprotocol.io) server that bridges your
AI assistant and the Proxmox VE API (`https://{host}:8006/api2/json`, token-authenticated):

```
┌──────────────────────────────┐     ┌──────────────────────────────────────────┐
│  MCP Client                  │     │  Proxmox DR MCP Server                   │
│  Claude · Cursor · Codex     │     │  (FastMCP, streamable-http on :8080)     │
└──────────────────────────────┘     └──────────────────────────────────────────┘
               │                                          │
           MCP (JSON-RPC)                                │   httpx + PVEAPIToken
           tool call / result                            │
               ▼                                          ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│   src/proxmox_dr_mcp/                                                         │
│   server.py  ──  registers tools + lazy ProxmoxClient(config)                 │
│   config.py  ──  pydantic-settings (env / .env)                               │
│                                                                               │
│   tools/                    proxmox/                  utils/                  │
│   ├─ preflight.py           ├─ client.py              ├─ types.py             │
│   ├─ snapshot.py            ├─ models.py              ├─ helpers.py           │
│   ├─ health.py              └─ exceptions.py          └─ ssh.py               │
│   └─ dr_workflow.py                                                           │
└───────────────────────────────────────────────────────────────────────────────┘
               │                                          │
        HTTPS (port 8006) · SSH (optional)                │
               ▼                                          ▼
                                    ┌───────────────────────────────────────────┐
                                    │                                           │
                                    │  Proxmox VE cluster                       │
                                    │  ├─ /nodes/<node>/qemu (VMs)              │
                                    │  ├─ /nodes/<node>/lxc (CTs)               │
                                    │  └─ /snapshot + /rollback                 │
                                    │                                           │
                                    └───────────────────────────────────────────┘
```

### Disaster Recovery Workflow

```
   ┌───────────────┐    ┌───────────────┐    ┌───────────────┐    ┌───────────────┐
   │ 1. Preflight  │──► │  2. Snapshot  │──► │   3. Verify   │──► │  4. Rollback  │
   │ storage space │    │  auto-named,  │    │    health:    │    │  on failure:  │
   │ recent backup │    │waits for UPID │    │status running │    │  restore to   │
   │  running VMs  │    │ task complete │    │  + resources  │    │   snapshot    │
   └───────────────┘    └───────────────┘    └───────────────┘    └───────────────┘
          │                    │                    │                    │
          ▼                    ▼                    ▼                    ▼
     proxmox_dr_     proxmox_dr_snapshot_      proxmox_dr_     proxmox_dr_snapshot_
      preflight          create · list        health_check            restore
```

The `proxmox_dr_safe_upgrade` tool chains **steps 1 → 2** (preflight gate, then
verified snapshots) and hands off to you for maintenance. After maintenance you run
`proxmox_dr_health_check` (**step 3**) — and if anything looks wrong,
`proxmox_dr_snapshot_restore` (**step 4**) rolls back. See the
[features table](#-features) for the exact tool names.

---

## ✨ Features

| Tool | Description |
|------|-------------|
| `proxmox_dr_preflight` | Check storage space, recent backups & running services before risky ops |
| `proxmox_dr_snapshot_create` | Create VM/LXC snapshots with auto-naming, descriptions & RAM state |
| `proxmox_dr_snapshot_list` | List all snapshots across the cluster with metadata |
| `proxmox_dr_snapshot_restore` | Rollback to a previous snapshot safely |
| `proxmox_dr_health_check` | Verify VMs/containers are running and healthy post-operation |
| `proxmox_dr_safe_upgrade` | **Safe preparation**: preflight → verified snapshots → upgrade instructions |

### Workflow: Safe Upgrade

The `proxmox_dr_safe_upgrade` tool prepares an upgrade in three safety-gated steps:

1. **Pre-flight** — checks storage space, backup freshness, running services
2. **Snapshot** — creates and waits for every pre-upgrade snapshot to complete
3. **Instructions** — tells you the upgrade is safe to proceed

After maintenance, run `proxmox_dr_health_check` separately. A one-shot tool cannot
verify a future upgrade, so it deliberately never reports post-upgrade health early.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+ (3.13 recommended — see `.python-version`)
- [uv](https://docs.astral.sh/uv/) (or pip)
- A Proxmox VE host with an API token configured

### Installation

**From source (recommended for development):**

```bash
git clone https://github.com/piyush97/proxmox-dr-mcp.git
cd proxmox-dr-mcp
uv sync                      # install deps into .venv
```

**From PyPI:**

```bash
pip install proxmox-dr-mcp
```

**Or install from source with pip:**

```bash
pip install -e .
```

### Configuration

Copy `.env.example` to `.env` and fill in your Proxmox API token:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PROXMOX_HOST` | ✅ | — | Proxmox VE hostname or IP |
| `PROXMOX_TOKEN_ID` | ✅ | — | API token ID (create at *Datacenter → Permissions → API Tokens*) |
| `PROXMOX_TOKEN_VALUE` | ✅ | — | API token secret |
| `PROXMOX_TOKEN_USER` | — | `root@pam` | Token user |
| `PROXMOX_VERIFY_SSL` | — | `true` | Set `false` only for a self-signed lab cert |
| `NODE` | — | `pve` | Default Proxmox node |
| `DEFAULT_SNAPSHOT_PREFIX` | — | `dr-` | Snapshot name prefix |
| `PORT` | — | `8080` | HTTP port |
| `LOG_LEVEL` | — | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

> **Note:** Credentials are validated lazily at tool-call time — the server boots
> without them and returns a clear "credentials not configured" error per tool.

### Running

```bash
# From a uv checkout
uv run proxmox-dr-mcp

# Via the pip entry point
proxmox-dr-mcp

# Via the Python module
python -m proxmox_dr_mcp
```

The server listens on **HTTP** (streamable-http transport) at
`http://localhost:8080/mcp` and exposes a `GET /health` endpoint. `PORT` is
configurable. For local stdio use in a desktop client, point the client at the
installed entry point instead — see [Client Configuration](#-client-configuration).

---

## 🔌 Client Configuration

### Claude Desktop

Add to `claude_desktop_config.json` (stdio):

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

> Requires the package to be installed in the same environment Claude Desktop
> runs in. Prefer `uvx proxmox-dr-mcp` when the server isn't on your global PATH.

### Cursor / Windsurf / VS Code (Cline)

Point the MCP client at the running HTTP server. Add to your MCP settings file:

```json
{
  "mcpServers": {
    "proxmox-dr": {
      "url": "http://localhost:8080/mcp",
      "env": {
        "PROXMOX_HOST": "192.168.1.100",
        "PROXMOX_TOKEN_ID": "my-token",
        "PROXMOX_TOKEN_VALUE": "my-secret"
      }
    }
  }
}
```

If the server is already running (e.g. deployed on MCPize or via Docker), only the
`url` is required — the Proxmox credentials are baked into the running server's env.

### Claude Code / Codex CLI

```bash
claude mcp add proxmox-dr -- uvx proxmox-dr-mcp \
  --env PROXMOX_HOST=192.168.1.100 \
  --env PROXMOX_TOKEN_ID=my-token \
  --env PROXMOX_TOKEN_VALUE=my-secret
```

### Docker

A production-ready [Dockerfile](Dockerfile) is included:

```bash
docker build -t proxmox-dr-mcp .
docker run -p 8080:8080 \
  -e PROXMOX_HOST=192.168.1.100 \
  -e PROXMOX_TOKEN_ID=my-token \
  -e PROXMOX_TOKEN_VALUE=my-secret \
  proxmox-dr-mcp
```

---

## 💬 Example Prompts

Once connected, try these:

| Prompt | What happens |
|--------|-------------|
| *"Run a pre-flight check before I upgrade my Proxmox host"* | Checks disk space, backups, running services |
| *"Create snapshots of all my VMs before the kernel update"* | Snapshots every VM with auto-naming |
| *"Run a safe upgrade workflow on VM 101"* | Pre-flight and verified snapshots before maintenance |
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
uv run python tests/test_safety.py

# Run live integration test (requires Proxmox env vars)
uv run python tests/test_live.py
```

CI runs `uv sync` plus the smoke and safety tests on every push — see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

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
