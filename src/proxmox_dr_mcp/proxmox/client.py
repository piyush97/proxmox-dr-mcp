"""Proxmox VE API client — async httpx-based, token-authenticated."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

from proxmox_dr_mcp.config import Settings
from proxmox_dr_mcp.proxmox.exceptions import (
    AuthenticationError,
    ConnectionError,
    NotFoundError,
    ProxmoxError,
    TaskError,
)
from proxmox_dr_mcp.proxmox.models import (
    ContainerStatus,
    Node,
    Snapshot,
    Storage,
    VMStatus,
)

log = logging.getLogger(__name__)


def _segment(value: str) -> str:
    """Encode one untrusted Proxmox API path segment."""
    return quote(value, safe="")


def _target_endpoint(target_type: str) -> str:
    if target_type == "vm":
        return "/qemu"
    if target_type == "lxc":
        return "/lxc"
    raise ValueError("target_type must be 'vm' or 'lxc'")


class ProxmoxClient:
    """Async HTTP client for the Proxmox VE API using token authentication.

    Uses a PVEAPIToken set via the ``Authorization`` header on every request.
    Base URL is ``https://{host}:8006/api2/json``.
    """

    def __init__(self, config: Settings) -> None:
        base_url = f"https://{config.proxmox_host}:8006/api2/json"
        token_value = (
            f"{config.proxmox_token_user}!"
            f"{config.proxmox_token_id}"
            f"={config.proxmox_token_value}"
        )
        self._auth_header = {"Authorization": f"PVEAPIToken={token_value}"}
        self._client = httpx.AsyncClient(
            base_url=base_url,
            verify=config.proxmox_verify_ssl,
            timeout=httpx.Timeout(30.0, connect=15.0),
        )

    async def __aenter__(self) -> ProxmoxClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    # ── Internal helpers ─────────────────────────────────────────────────

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Perform a GET request and return the parsed ``data`` field."""
        try:
            resp = await self._client.get(
                path, params=params, headers=self._auth_header
            )
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Unable to connect to Proxmox API at {self._client.base_url}: {exc}"
            ) from exc

        return self._check_response(resp)

    async def _post(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Perform a POST request and return the parsed ``data`` field."""
        try:
            resp = await self._client.post(
                path, data=data, params=params, headers=self._auth_header
            )
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Unable to connect to Proxmox API at {self._client.base_url}: {exc}"
            ) from exc

        return self._check_response(resp)

    async def _delete(self, path: str) -> Any:
        """Perform a DELETE request and return the parsed ``data`` field."""
        try:
            resp = await self._client.delete(path, headers=self._auth_header)
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Unable to connect to Proxmox API at {self._client.base_url}: {exc}"
            ) from exc

        return self._check_response(resp)

    @staticmethod
    def _check_response(resp: httpx.Response) -> Any:
        """Validate the HTTP response and return the JSON ``data`` field.

        Raises the appropriate custom exception on error status codes.
        """
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            status = exc.response.status_code
            method = exc.request.method if exc.request else "?"
            path = str(exc.request.url) if exc.request else "?"

            if status == 401:
                raise AuthenticationError(
                    f"Proxmox API authentication failed (HTTP {status}): {detail}"
                ) from exc
            if status == 404:
                raise NotFoundError(
                    f"Resource not found: {method} {path}"
                ) from exc
            raise ProxmoxError(
                f"API error {status} for {method} {path}: {detail}"
            ) from exc

        body = resp.json()
        return body.get("data", body)

    # ── Nodes ────────────────────────────────────────────────────────────

    async def get_nodes(self) -> list[Node]:
        """List all cluster nodes."""
        data = await self._get("/nodes")
        return [Node(**n) for n in data]

    # ── Storage ──────────────────────────────────────────────────────────

    async def get_storage(self, node: str) -> list[Storage]:
        """List storage devices available on *node*."""
        data = await self._get(f"/nodes/{_segment(node)}/storage")
        return [Storage(**s, node=node) for s in data]

    async def get_storage_content(
        self, node: str, storage: str
    ) -> list[dict[str, Any]]:
        """List content (backups, ISO, templates) on a *storage* of *node*."""
        data = await self._get(
            f"/nodes/{_segment(node)}/storage/{_segment(storage)}/content"
        )
        return data  # list of raw dicts - shape varies by content type

    # ── VMs ──────────────────────────────────────────────────────────────

    async def get_vms(self, node: str) -> list[VMStatus]:
        """List QEMU virtual machines on *node*."""
        data = await self._get(f"/nodes/{_segment(node)}/qemu")
        return [VMStatus(**vm, node=node) for vm in data]

    async def get_vm_status(self, node: str, vmid: int) -> VMStatus:
        """Get detailed status of a single QEMU VM."""
        data = await self._get(
            f"/nodes/{_segment(node)}/qemu/{vmid}/status/current"
        )
        return VMStatus(**data, node=node)

    # ── Containers ───────────────────────────────────────────────────────

    async def get_containers(self, node: str) -> list[ContainerStatus]:
        """List LXC containers on *node*."""
        data = await self._get(f"/nodes/{_segment(node)}/lxc")
        return [ContainerStatus(**ct, node=node) for ct in data]

    async def get_ct_status(self, node: str, vmid: int) -> ContainerStatus:
        """Get detailed status of a single LXC container."""
        data = await self._get(
            f"/nodes/{_segment(node)}/lxc/{vmid}/status/current"
        )
        return ContainerStatus(**data, node=node)

    # ── Snapshots ────────────────────────────────────────────────────────

    async def create_snapshot(
        self,
        node: str,
        vmid: int,
        snapname: str,
        description: str = "",
        vmstate: bool = False,
        target_type: str = "vm",
    ) -> str:
        """Create a VM/LXC snapshot.

        *target_type* — ``"vm"`` (QEMU, default) or ``"lxc"``.
        Returns the task UPID string.
        """
        endpoint = _target_endpoint(target_type)
        body: dict[str, Any] = {"snapname": snapname}
        if description:
            body["description"] = description
        if vmstate:
            body["vmstate"] = 1
        data = await self._post(
            f"/nodes/{_segment(node)}{endpoint}/{vmid}/snapshot", data=body
        )
        return str(data) if data else ""

    async def list_snapshots(self, node: str, vmid: int, target_type: str = "vm") -> list[Snapshot]:
        """List all snapshots for a VM or LXC.

        *target_type* — ``"vm"`` (QEMU, default) or ``"lxc"``.
        """
        endpoint = _target_endpoint(target_type)
        data = await self._get(f"/nodes/{_segment(node)}{endpoint}/{vmid}/snapshot")
        return [
            Snapshot(**s, vmid=vmid, node=node)
            for s in data
            if s.get("name") and s["name"] != "current"
        ]

    async def rollback_snapshot(
        self, node: str, vmid: int, snapname: str, target_type: str = "vm"
    ) -> str:
        """Roll back a VM/LXC to *snapname*.

        *target_type* — ``"vm"`` (QEMU, default) or ``"lxc"``.
        Returns the task UPID string.
        """
        endpoint = _target_endpoint(target_type)
        data = await self._post(
            f"/nodes/{_segment(node)}{endpoint}/{vmid}/snapshot/{_segment(snapname)}/rollback",
            data={"snapname": snapname},
        )
        return str(data) if data else ""

    async def delete_snapshot(
        self, node: str, vmid: int, snapname: str, target_type: str = "vm"
    ) -> str:
        """Delete a VM/LXC snapshot.

        *target_type* — ``"vm"`` (QEMU, default) or ``"lxc"``.
        Returns the task UPID string.
        """
        endpoint = _target_endpoint(target_type)
        data = await self._delete(
            f"/nodes/{_segment(node)}{endpoint}/{vmid}/snapshot/{_segment(snapname)}"
        )
        return str(data) if data else ""

    # ── Task polling ────────────────────────────────────────────────────

    async def poll_task(self, node: str, upid: str) -> dict[str, Any]:
        """Get current status of a Proxmox task."""
        data = await self._get(f"/nodes/{_segment(node)}/tasks/{_segment(upid)}/status")
        return data if isinstance(data, dict) else {}

    async def wait_for_task(
        self, node: str, upid: str, timeout: float = 30.0, poll_interval: float = 1.0
    ) -> dict[str, Any]:
        """Poll task until it completes or times out."""
        import asyncio
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            status = await self.poll_task(node, upid)
            if status.get("status") == "stopped":
                if status.get("exitstatus") != "OK":
                    raise TaskError(
                        f"Task {upid[:40]}... failed: {status.get('exitstatus', 'unknown')}",
                        task_upid=upid,
                    )
                return status
            if asyncio.get_event_loop().time() >= deadline:
                raise TimeoutError(f"Task {upid[:40]}... did not complete within {timeout}s")
            await asyncio.sleep(poll_interval)
