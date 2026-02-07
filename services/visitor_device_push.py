# services/visitor_device_push.py

from datetime import datetime

from db import get_conn
from services.devices import get_device_by_id

from services.device_user_push_api import (
    push_userinfo,
    push_face,
    mark_device_user_status,
)


DEVICE_ROLE = "normal"  # Hikvision-safe


def push_visitor_to_device(visitor_id: int) -> dict:
    """
    Manually push a visitor to their assigned device.
    Explicit action only. No automation.
    """

    conn = get_conn()

    vp = conn.execute(
        """
        SELECT
            id,
            visitor_employee_no,
            visitor_name,
            device_id,
            face_path
        FROM visitor_passes
        WHERE id = ?
          AND status = 'active'
        """,
        (visitor_id,),
    ).fetchone()

    if not vp:
        conn.close()
        return {"status": "failed", "reason": "visitor_not_active"}

    device = get_device_by_id(vp["device_id"])
    if not device:
        conn.close()
        return {"status": "failed", "reason": "device_not_found"}

    try:
        # -----------------------------
        # Push user (role resolved here)
        # -----------------------------
        push_userinfo(
            device=device,
            employee_no=vp["visitor_employee_no"],
            name=vp["visitor_name"],
            user_type=DEVICE_ROLE,
        )

        # -----------------------------
        # Optional face push
        # -----------------------------
        if vp["face_path"]:
            push_face(
                device=device,
                user={
                    "employee_no": vp["visitor_employee_no"],
                    "face_path": vp["face_path"],
                },
            )

        # -----------------------------
        # Track per-device state
        # -----------------------------
        mark_device_user_status(
            device_id=device["id"],
            employee_no=vp["visitor_employee_no"],
            name=vp["visitor_name"],
            device_role=DEVICE_ROLE,
        )

        conn.execute(
            """
            INSERT INTO visitor_events (visitor_id, event, meta)
            VALUES (?, 'pushed_to_device', json(?))
            """,
            (visitor_id, '{"source":"manual"}'),
        )

        conn.commit()
        conn.close()

        return {"status": "ok"}

    except Exception as e:
        mark_device_user_status(
            device_id=device["id"],
            employee_no=vp["visitor_employee_no"],
            device_role=DEVICE_ROLE,
            status="failed",
            pushed_at=datetime.utcnow(),
        )

        conn.close()
        return {"status": "failed", "reason": str(e)}
