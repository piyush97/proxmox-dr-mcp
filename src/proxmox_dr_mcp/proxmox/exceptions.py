"""Custom exceptions for Proxmox operations."""

from __future__ import annotations


class ProxmoxError(Exception):
    """Base exception for all Proxmox-related errors."""


class AuthenticationError(ProxmoxError):
    """Raised when Proxmox API authentication fails."""


class ConnectionError(ProxmoxError):
    """Raised when unable to connect to the Proxmox API."""


class NotFoundError(ProxmoxError):
    """Raised when a requested resource does not exist."""


class TaskError(ProxmoxError):
    """Raised when a Proxmox task finishes with an error status."""

    def __init__(self, message: str, task_upid: str | None = None) -> None:
        self.task_upid = task_upid
        super().__init__(message)


class ValidationError(ProxmoxError):
    """Raised when input validation fails."""


class SSHOperationError(ProxmoxError):
    """Raised when a remote SSH operation fails."""

    def __init__(
        self,
        message: str,
        host: str | None = None,
        exit_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        self.host = host
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(message)