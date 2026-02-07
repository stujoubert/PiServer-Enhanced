# /opt/attendance/services/devices.py
from __future__ import annotations

from typing import Optional, Dict, Any
from db import get_conn


def get_primary_fdlib_device() -> Optional[Dict[str, Any]]:
    """
    Returns a single active device marked as supports_fdlib=1.

    Selection is deterministic:
      1) devices.supports_fdlib=1 AND active=1
      2) Prefer most recently seen (last_seen_at), then lowest id
    """
    conn = get_conn()
    row = conn.execute(
        """
        SELECT id, name, ip, username, password, active,
               supports_fdlib, supports_user_sync, last_seen_at
        FROM devices
        WHERE active = 1 AND supports_fdlib = 1
        ORDER BY
            CASE WHEN last_seen_at IS NULL THEN 1 ELSE 0 END,
            last_seen_at DESC,
            id ASC
        LIMIT 1
        """
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def touch_device_seen(device_id: int) -> None:
    """Update last_seen_at when a device is successfully contacted."""
    conn = get_conn()
    conn.execute(
        "UPDATE devices SET last_seen_at = datetime('now') WHERE id = ?",
        (device_id,),
    )
    conn.commit()
    conn.close()

def get_fdlib_devices() -> list[Dict[str, Any]]:
    """
    Return ALL active FDLib-capable devices with credentials.
    Used by batch jobs (daily_user_sync).
    """
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT id, name, ip, username, password, active,
               supports_fdlib, supports_user_sync, last_seen_at
        FROM devices
        WHERE active = 1
          AND supports_fdlib = 1
          AND ip IS NOT NULL AND TRIM(ip) <> ''
          AND username IS NOT NULL AND TRIM(username) <> ''
          AND password IS NOT NULL AND TRIM(password) <> ''
        ORDER BY
            CASE WHEN last_seen_at IS NULL THEN 1 ELSE 0 END,
            last_seen_at DESC,
            id ASC
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_any_active_device_with_creds() -> Optional[Dict[str, Any]]:
    """
    Fallback device selection (non-FDLib).
    Useful for user sync, event fetch, etc.
    """
    conn = get_conn()
    row = conn.execute(
        """
        SELECT id, name, ip, username, password, active, last_seen_at
        FROM devices
        WHERE active = 1
          AND ip IS NOT NULL AND TRIM(ip) <> ''
          AND username IS NOT NULL AND TRIM(username) <> ''
          AND password IS NOT NULL AND TRIM(password) <> ''
        ORDER BY
            CASE WHEN last_seen_at IS NULL THEN 1 ELSE 0 END,
            last_seen_at DESC,
            id ASC
        LIMIT 1
        """
    ).fetchone()
    conn.close()
    return dict(row) if row else None
