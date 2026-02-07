from db import get_conn
from devices.hikvision_isapi import HikvisionISAPI
import requests

def load_face_bytes(employee_id: str) -> bytes | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT image_path FROM user_faces WHERE employee_id = ?",
        (employee_id,),
    ).fetchone()
    conn.close()

    if not row:
        return None

    with open(row["image_path"], "rb") as f:
        return f.read()


def push_users_to_device(device_id: int, employee_ids: list[str]):
    conn = get_conn()

    device = conn.execute(
        """
        SELECT ip, username, password
        FROM devices
        WHERE id = ?
        """,
        (device_id,),
    ).fetchone()

    if not device:
        raise RuntimeError("Device not found")

    api = HikvisionISAPI(
        ip=device["ip"],
        username=device["username"],
        password=device["password"],
    )

    results = []

    for emp_id in employee_ids:
        user = conn.execute(
            """
            SELECT employee_id, name
            FROM users
            WHERE employee_id = ?
            """,
            (emp_id,),
        ).fetchone()

        if not user:
            results.append({
                "employee_id": emp_id,
                "status": "failed",
                "reason": "user_not_found",
            })
            continue

        try:
            api.create_or_update_user(user["employee_id"], user["name"])

            face = load_face_bytes(user["employee_id"])
            if not face:
                results.append({
                    "employee_id": emp_id,
                    "status": "warning",
                    "reason": "no_face",
                })
                continue

            api.upload_face(user["employee_id"], face)

            results.append({
                "employee_id": emp_id,
                "status": "ok",
            })

        except Exception as e:
            results.append({
                "employee_id": emp_id,
                "status": "failed",
                "reason": str(e),
            })

    conn.close()
    return results
