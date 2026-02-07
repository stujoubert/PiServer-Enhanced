# /opt/attendance/routes/device_users.py

import json
import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from requests.auth import HTTPDigestAuth
from flask import Blueprint, render_template, request, flash, redirect, url_for

from db import get_conn
from authz import login_required, role_required

bp = Blueprint("device_users", __name__, url_prefix="/devices/users")

# Local cache directory (Option A)
FACE_CACHE_DIR = Path("/opt/attendance/static/uploads/device_faces")


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _ensure_face_cache_dir() -> None:
    FACE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _as_http_url(maybe_url: str) -> Optional[str]:
    if not maybe_url:
        return None
    u = str(maybe_url).strip()
    if not u:
        return None
    if u.startswith("http://") or u.startswith("https://"):
        return u
    if u.startswith("/"):
        return request.host_url.rstrip("/") + u
    return None


def _download_to_file(url: str, dest_path: Path, timeout: int = 20) -> bool:
    try:
        r = requests.get(url, stream=True, timeout=timeout)
        if r.status_code >= 400:
            return False

        tmp = dest_path.with_suffix(dest_path.suffix + ".tmp")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1024 * 64):
                if chunk:
                    f.write(chunk)

        if tmp.exists() and tmp.stat().st_size > 0:
            tmp.replace(dest_path)
            return True

        tmp.unlink(missing_ok=True)
        return False
    except Exception:
        return False


def _get_local_face_path(conn: sqlite3.Connection, employee_id: str) -> Optional[str]:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(user_faces);").fetchall()]
    if "local_path" not in cols:
        return None
    row = conn.execute(
        "SELECT local_path FROM user_faces WHERE employee_id = ?",
        (employee_id,),
    ).fetchone()
    if not row:
        return None
    return row["local_path"] or None


def _set_local_face_path(conn: sqlite3.Connection, employee_id: str, local_path: str) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(user_faces);").fetchall()]
    if "local_path" not in cols:
        return
    conn.execute(
        """
        UPDATE user_faces
        SET local_path = ?, local_updated_at = datetime('now')
        WHERE employee_id = ?
        """,
        (local_path, employee_id),
    )
    conn.commit()


def _materialize_face_local(
    conn: sqlite3.Connection,
    employee_id: str,
    picture_url: Optional[str],
) -> Optional[Path]:
    _ensure_face_cache_dir()
    emp = str(employee_id).strip()
    if not emp:
        return None

    lp = _get_local_face_path(conn, emp)
    if lp:
        p = Path(lp)
        if p.exists() and p.stat().st_size > 0:
            return p

    abs_url = _as_http_url(picture_url or "")
    if not abs_url:
        return None

    dest = FACE_CACHE_DIR / f"{emp}.jpg"
    if _download_to_file(abs_url, dest):
        _set_local_face_path(conn, emp, str(dest))
        return dest

    return None


# -------------------------------------------------
# ISAPI helpers
# -------------------------------------------------

def isapi_create_user(
    base_url: str,
    username: str,
    password: str,
    employee_no: str,
    name: str,
) -> Tuple[bool, str]:
    url = f"{base_url}/ISAPI/AccessControl/UserInfo/SetUp?format=json"
    payload = {
        "UserInfo": {
            "employeeNo": str(employee_no),
            "name": name or str(employee_no),
            "userType": "normal",
            "Valid": {
                "enable": True,
                "beginTime": "2017-08-01T00:00:00",
                "endTime": "2035-08-01T23:59:59",
                "timeType": "local",
            },
            "doorRight": "1",
            "RightPlan": [{"doorNo": 1, "planTemplateNo": "1"}],
        }
    }

    try:
        r = requests.put(
            url,
            auth=HTTPDigestAuth(username, password),
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=20,
        )
        return r.status_code < 400, r.text
    except Exception as e:
        return False, str(e)


def isapi_face_exists(
    base_url: str,
    username: str,
    password: str,
    fdid: str,
    fpid: str,
) -> bool:
    url = f"{base_url}/ISAPI/Intelligent/FDLib/FDSearch?format=json"
    payload = {
        "FDSearchCond": {
            "searchID": "1",
            "searchResultPosition": 0,
            "maxResults": 1,
            "faceLibType": "blackFD",
            "FDID": str(fdid),
            "FPID": str(fpid),
        }
    }

    try:
        r = requests.post(
            url,
            auth=HTTPDigestAuth(username, password),
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=15,
        )
        if r.status_code >= 400:
            return False

        data = r.json()
        root = data.get("FDSearch") or data
        matches = root.get("numOfMatches") or 0
        return int(matches) > 0
    except Exception:
        return False


def isapi_upload_face_multipart(
    base_url: str,
    username: str,
    password: str,
    employee_no: str,
    name: str,
    image_path: Path,
    fdid: str = "1",
) -> Tuple[bool, str]:
    url = f"{base_url}/ISAPI/Intelligent/FDLib/FaceDataRecord?format=json"

    face_data = {
        "faceLibType": "blackFD",
        "FDID": str(fdid),
        "FPID": str(employee_no),
        "name": name or str(employee_no),
    }

    try:
        with open(image_path, "rb") as f:
            files = {"FaceImage": (image_path.name, f, "image/jpeg")}
            data = {"FaceDataRecord": json.dumps(face_data, ensure_ascii=False)}

            r = requests.post(
                url,
                auth=HTTPDigestAuth(username, password),
                files=files,
                data=data,
                timeout=30,
            )

        return r.status_code < 400, r.text
    except Exception as e:
        return False, str(e)


# -------------------------------------------------
# Routes
# -------------------------------------------------

@bp.route("/push", methods=["GET", "POST"])
@login_required
@role_required("admin")
def push_users():
    conn = get_conn()
    conn.row_factory = sqlite3.Row

    devices = conn.execute(
        """
        SELECT id, name, ip, username, password
        FROM devices
        WHERE active = 1
        ORDER BY name
        """
    ).fetchall()

    target_device_id = request.args.get("device_id") or request.form.get("device_id") or ""
    selected_target = None
    users: List[sqlite3.Row] = []

    if target_device_id:
        selected_target = conn.execute(
            "SELECT * FROM devices WHERE id = ? AND active = 1",
            (target_device_id,),
        ).fetchone()

    if selected_target:
        users = conn.execute(
            """
            SELECT
                u.employee_id,
                u.name,
                uf.picture_url,
                uf.local_path
            FROM users u
            LEFT JOIN user_faces uf
              ON uf.id = (
                  SELECT id
                  FROM user_faces
                  WHERE employee_id = u.employee_id
                  ORDER BY COALESCE(local_updated_at, created_at) DESC
                  LIMIT 1
              )
            WHERE u.is_active = 1
            ORDER BY CAST(u.employee_id AS INTEGER)
            """
        ).fetchall()

    if request.method == "POST":
        user_ids = set(request.form.getlist("user_ids[]"))

        if not selected_target:
            flash("No target device selected", "danger")
            conn.close()
            return redirect(url_for("device_users.push_users"))

        if not user_ids:
            flash("Please select at least one user", "danger")
            conn.close()
            return redirect(url_for("device_users.push_users", device_id=target_device_id))

        base_url = f"http://{selected_target['ip']}"
        dev_user = selected_target["username"]
        dev_pass = selected_target["password"]

        pushed = 0
        faces_ok = 0
        faces_attempted = 0
        fdid = (request.form.get("fdid") or "1").strip() or "1"

        for u in users:
            emp = str(u["employee_id"])
            if emp not in user_ids:
                continue

            ok_user, _ = isapi_create_user(
                base_url,
                dev_user,
                dev_pass,
                emp,
                u["name"] or emp,
            )
            if ok_user:
                pushed += 1

            local_face = _materialize_face_local(
                conn,
                emp,
                u["picture_url"],
            )

            if not local_face or not local_face.exists():
                continue

            faces_attempted += 1

            if isapi_face_exists(
                base_url,
                dev_user,
                dev_pass,
                fdid,
                emp,
            ):
                faces_ok += 1
                continue

            ok_face, _ = isapi_upload_face_multipart(
                base_url,
                dev_user,
                dev_pass,
                emp,
                u["name"] or emp,
                local_face,
                fdid=fdid,
            )
            if ok_face:
                faces_ok += 1

        flash(
            f"Pushed {pushed}/{len(user_ids)} users. "
            f"Faces uploaded: {faces_ok}/{faces_attempted}.",
            "success",
        )
        conn.close()
        return redirect(url_for("device_users.push_users", device_id=target_device_id))

    conn.close()
    return render_template(
        "device_users_push.html",
        devices=devices,
        selected_device=selected_target,
        users=users,
    )
