"""Application configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Proxmox DR MCP server configuration.

    Loaded from environment variables. Every field maps to a corresponding
    environment variable by uppercasing the field name (e.g. ``proxmox_host``
    reads ``PROXMOX_HOST``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Proxmox connection (optional — validated at tool time) ---
    proxmox_host: str | None = Field(
        default=None,
        description="Proxmox VE hostname or IP address",
    )
    proxmox_token_user: str = Field(
        default="root@pam",
        description="Proxmox VE API token user (e.g. root@pam)",
    )
    proxmox_token_id: str | None = Field(
        default=None,
        description="Proxmox VE API token ID",
    )
    proxmox_token_value: str | None = Field(
        default=None,
        description="Proxmox VE API token secret value",
    )
    proxmox_verify_ssl: bool = Field(
        default=False,
        description="Verify TLS certificates for Proxmox API",
    )

    # --- DR settings ---
    node: str = Field(
        default="pve",
        description="Default Proxmox node name",
    )
    default_snapshot_prefix: str = Field(
        default="dr-",
        description="Prefix for DR snapshots",
    )

    # --- Logging ---
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )


@lru_cache(maxsize=1)
def get_config() -> Settings:
    """Return the singleton Settings instance.

    Cached after first call so all consumers share the same validated config.
    """
    return Settings()