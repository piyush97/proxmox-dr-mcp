"""SSH utilities for remote Proxmox operations."""

from __future__ import annotations

import asyncio
import logging

from pathlib import Path

from proxmox_dr_mcp.proxmox.exceptions import SSHOperationError

log = logging.getLogger(__name__)


async def run_ssh(
    host: str,
    command: str,
    ssh_key_path: str | Path | None = None,
    ssh_user: str = "root",
    timeout: int = 60,
) -> str:
    """Run a command on a remote host via SSH.

    Returns stdout on success.
    Raises SSHOperationError on non-zero exit or connection failure.
    """
    key_path = Path(ssh_key_path).expanduser().resolve() if ssh_key_path else None
    ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new"]

    if key_path and key_path.exists():
        ssh_cmd.extend(["-i", str(key_path)])

    ssh_cmd.extend(["-o", "ConnectTimeout=15", f"{ssh_user}@{host}"])
    ssh_cmd.append(command)

    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *ssh_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ),
            timeout=timeout,
        )
        stdout, stderr = await proc.communicate()
    except asyncio.TimeoutError:
        raise SSHOperationError(
            f"SSH command timed out after {timeout}s",
            host=host,
        )
    except FileNotFoundError:
        raise SSHOperationError(
            "SSH binary not found. Ensure openssh-client is installed.",
            host=host,
        )
    except OSError as exc:
        raise SSHOperationError(
            f"SSH connection failed: {exc}", host=host
        ) from exc

    stdout_str = stdout.decode("utf-8", errors="replace").strip()
    stderr_str = stderr.decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        raise SSHOperationError(
            f"SSH command exited with code {proc.returncode}",
            host=host,
            exit_code=proc.returncode,
            stderr=stderr_str,
        )

    return stdout_str


async def run_ssh_scp(
    host: str,
    local_path: str | Path,
    remote_path: str,
    ssh_key_path: str | Path | None = None,
    ssh_user: str = "root",
    timeout: int = 120,
) -> None:
    """Copy a file to a remote host via SCP."""
    key_path = Path(ssh_key_path).expanduser().resolve() if ssh_key_path else None
    scp_cmd = ["scp", "-o", "StrictHostKeyChecking=accept-new"]

    if key_path and key_path.exists():
        scp_cmd.extend(["-i", str(key_path)])

    scp_cmd.extend(["-o", "ConnectTimeout=15"])
    scp_cmd.append(str(local_path))
    scp_cmd.append(f"{ssh_user}@{host}:{remote_path}")

    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *scp_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ),
            timeout=timeout,
        )
        _, stderr = await proc.communicate()
    except asyncio.TimeoutError:
        raise SSHOperationError(
            f"SCP transfer timed out after {timeout}s", host=host
        )
    except FileNotFoundError:
        raise SSHOperationError(
            "SCP binary not found. Ensure openssh-client is installed.",
            host=host,
        )
    except OSError as exc:
        raise SSHOperationError(
            f"SCP connection failed: {exc}", host=host
        ) from exc

    stderr_str = stderr.decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        raise SSHOperationError(
            f"SCP exited with code {proc.returncode}",
            host=host,
            exit_code=proc.returncode,
            stderr=stderr_str,
        )

    log.debug("SCP %s -> %s:%s done", local_path, host, remote_path)


async def check_remote_proxmox(
    host: str,
    ssh_key_path: str | Path | None = None,
    ssh_user: str = "root",
) -> bool:
    """Check if a remote host is reachable and has pvesh available."""
    try:
        output = await run_ssh(
            host,
            "which pvesh && pvesh version 2>/dev/null || true",
            ssh_key_path=ssh_key_path,
            ssh_user=ssh_user,
            timeout=15,
        )
        return "pvesh" in output
    except SSHOperationError:
        return False