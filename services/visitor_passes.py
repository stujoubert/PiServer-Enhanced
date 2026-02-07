# services/visitor_passes.py

import json
import uuid
from datetime import datetime
from db import get_conn


# --------------------------------------------------
# Helpers
# --------------------------------------------------
def _normalize_dt(value: str) -> str:
    """
    Normalize ISO / datetime-local strings to SQLite DATETIME.
    Raises ValueError if invalid.
    """
    if not value:
        raise ValueError("datetime value is required")

    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        raise ValueError(f"Invalid datetime format: {value}")


# --------------------------------------------------
# Create visitor pass
# --------------------------------------------------
def create_visitor_pass(
    *,
    visitor_name: str,
    visitor_employee_no: str,
    device_id: int,
    valid_until: str,
    issued_by_employee_id: str = "system",
    face_image_path: str | None = None,
    valid_from: str | None = None,
    qr_token: str | None = None,
):
    # ---- normalize datetimes (schema requires NOT NULL) ----
    valid_until = _normalize_dt(valid_until)

    if valid_from:
        valid_from = _normalize_dt(valid_from)
    else:
        valid_from = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    if not qr_token:
        qr_token = str(uuid.uuid4())

    # schema requires expires_at (NOT NULL)
    expires_at = valid_until

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO visitor_passes (
            issued_by_employee_id,
            device_id,
            visitor_name,
            visitor_employee_no,
            face_image_path,
            qr_token,
            valid_from,
            valid_until,
            expires_at,
            revoked,
            status
        )
        VALUES (?,?,?,?,?,?,?,?,?,0,'active')
        """,
        (
            issued_by_employee_id,
            device_id,
            visitor_name,
            visitor_employee_no,
            face_image_path,
            qr_token,
            valid_from,
            valid_until,
            expires_at,
        ),
    )

    visitor_id = cur.lastrowid

    # ---- IMPORTANT FIX: JSON MUST BE SERIALIZED IN PYTHON ----
    cur.execute(
        """
        INSERT INTO visitor_events (visitor_id, event, meta)
        VALUES (?, ?, ?)
        """,
        (
            visitor_id,
            "created",
            json.dumps({
                "device_id": device_id,
                "issued_by": issued_by_employee_id,
            }),
        ),
    )

    conn.commit()
    conn.close()

    return visitor_id


# --------------------------------------------------
# Revoke visitor pass
# --------------------------------------------------
def revoke_visitor_pass(visitor_id: int, revoked_by: str, reason: str | None = None):
    conn = get_conn()

    conn.execute(
        """
        UPDATE visitor_passes
        SET status = 'revoked', revoked = 1
        WHERE id = ?
        """,
        (visitor_id,),
    )

    _log_event(
        conn,
        visitor_id,
        "revoked",
        {
            "revoked_by": revoked_by,
            "reason": reason or "",
        },
    )

    conn.commit()
    conn.close()


# --------------------------------------------------
# Expire visitor passes (timer-safe)
# --------------------------------------------------
def expire_visitor_passes(limit: int = 500) -> int:
    conn = get_conn()
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT id
        FROM visitor_passes
        WHERE status = 'active'
          AND expires_at <= datetime('now')
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    count = 0

    for (visitor_id,) in rows:
        conn.execute(
            """
            UPDATE visitor_passes
            SET status = 'expired'
            WHERE id = ?
            """,
            (visitor_id,),
        )

        _log_event(
            conn,
            visitor_id,
            "expired",
            {"expired_by": "system"},
        )

        count += 1

    conn.commit()
    conn.close()
    return count


# --------------------------------------------------
# Fetch helpers
# --------------------------------------------------
def get_visitor_pass(visitor_id: int):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM visitor_passes WHERE id = ?",
        (visitor_id,),
    ).fetchone()
    conn.close()
    return row


def list_visitor_passes():
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT *
        FROM visitor_passes
        ORDER BY
            COALESCE(created_at, valid_from) DESC,
            id DESC
        """
    ).fetchall()
    conn.close()
    return rows


def get_visitor_events(visitor_id: int):
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT *
        FROM visitor_events
        WHERE visitor_id = ?
        ORDER BY event_at DESC
        """,
        (visitor_id,),
    ).fetchall()
    conn.close()
    return rows


# --------------------------------------------------
# Internal audit helper
# --------------------------------------------------
def _log_event(conn, visitor_id: int, event: str, meta: dict):
    conn.execute(
        """
        INSERT INTO visitor_events (visitor_id, event, meta)
        VALUES (?, ?, ?)
        """,
        (visitor_id, event, json.dumps(meta or {})),
    )


# --------------------------------------------------
# Visitor employee number generator
# --------------------------------------------------
def generate_visitor_employee_no(conn) -> str:
    today = datetime.now().strftime("%Y%m%d")

    row = conn.execute(
        """
        SELECT COUNT(*) + 1 AS seq
        FROM visitor_passes
        WHERE visitor_employee_no LIKE ?
        """,
        (f"V-{today}-%",),
    ).fetchone()

    seq = row["seq"] if row else 1
    return f"V-{today}-{seq:03d}"
