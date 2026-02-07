# services/device_user_push_api.py
#
# SAFE compatibility layer for visitor push
# Fully aligned with existing device_users schema

from services.device_push import HikvisionISAPI
from db import get_conn


def push_userinfo(device, employee_no: str, name: str, user_type: str):
    """
    Push/update a user to a Hikvision device.
    user_type must be Hikvision-safe: 'normal' or 'admin'
    """
    api = HikvisionISAPI(
        ip=device["ip"],
        username=device["username"],
        password=device["password"],
    )

    return api.create_or_update_user(
        employee_no=employee_no,
        name=name,
        user_type=user_type,
    )


def push_face(device, user: dict):
    """
    Push face image if present.
    """
    api = HikvisionISAPI(
        ip=device["ip"],
        username=device["username"],
        password=device["password"],
    )

    return api.upload_face(
        employee_no=user["employee_no"],
        image_path=user["face_path"],
    )


def mark_device_user_status(
    device_id: int,
    employee_no: str,
    name: str,
    device_role: str,
):
    """
    Persist visitor into device_users
    using EXISTING schema only.
    """

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO device_users (
            device_id,
            employee_id,
            name,
            role,
            enabled
        )
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(device_id, employee_id)
        DO UPDATE SET
            name = excluded.name,
            role = excluded.role,
            enabled = 1
        """,
        (
            device_id,
            employee_no,
            name,
            device_role,
        ),
    )
    conn.commit()
    conn.close()
