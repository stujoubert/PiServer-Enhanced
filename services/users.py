from db import get_conn
import base64
from PIL import Image
from io import BytesIO
from pathlib import Path

# -------------------------------------------------------------------
# USERS + SCHEDULE TEMPLATE RESOLUTION
# -------------------------------------------------------------------

def list_users_with_templates():
    """
    Used by dashboard / payroll / reports.
    Returns users with their assigned schedule TEMPLATE (if any).
    """

    conn = get_conn()
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT
            u.id AS user_id,
            u.employee_id,
            COALESCE(u.name, u.employee_id, CAST(u.id AS TEXT)) AS name,
            st.id AS template_id,
            st.name AS template_name
        FROM users u
        LEFT JOIN user_schedule_assignments usa
            ON usa.user_id = u.id
        LEFT JOIN schedule_templates st
            ON st.id = usa.template_id
        ORDER BY
            CASE
                WHEN u.employee_id GLOB '[0-9]*'
                THEN CAST(u.employee_id AS INTEGER)
                ELSE 999999999
            END,
            u.employee_id,
            u.id
        """
    ).fetchall()

    conn.close()
    return rows


def get_user_schedule_template(user_id: int):
    """
    Returns the assigned schedule TEMPLATE for a single user.
    Used by attendance / payroll calculations.
    """

    conn = get_conn()
    cur = conn.cursor()

    row = cur.execute(
        """
        SELECT
            st.id,
            st.name
        FROM user_schedule_assignments usa
        JOIN schedule_templates st
            ON st.id = usa.template_id
        WHERE usa.user_id = ?
        """,
        (user_id,),
    ).fetchone()

    conn.close()
    return row

def list_users():
    """
    Returns all users as a list of tuples.
    Expected format: (employee_id, name, active)
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT employee_id, name, active
        FROM users
        ORDER BY employee_id ASC
    """)

    rows = cur.fetchall()
    conn.close()
    return rows

def get_next_employee_id() -> int:
    """
    Returns the next available employee_id as an integer.
    Defaults to 1 if no users exist.
    """
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT MAX(CAST(employee_id AS INTEGER)) FROM users"
        ).fetchone()
        return (row[0] or 0) + 1
    finally:
        conn.close()



# ------------------------------------
#  FACE IMPORT MOBILE / PC
# ------------------------------------


USER_FACE_DIR = Path("/opt/attendance/static/uploads/device_faces")

def save_user_face(employee_no: str, data_url: str) -> None:
    USER_FACE_DIR.mkdir(parents=True, exist_ok=True)

    header, encoded = data_url.split(",", 1)
    image_bytes = base64.b64decode(encoded)

    if len(image_bytes) > 200 * 1024:
        raise ValueError("Face image exceeds 200KB limit")

    img = Image.open(BytesIO(image_bytes)).convert("RGB")

    w, h = img.size
    if w < 300 or h < 300:
        raise ValueError("Face image resolution too small")

    # Normalize size
    img = img.resize((640, 640))

    filename = f"{employee_no}.jpg"
    file_path = USER_FACE_DIR / filename

    img.save(file_path, format="JPEG", quality=90)

    # --------------------------------------------------
    # REGISTER FACE (SAME CONVENTION AS EVERYTHING ELSE)
    # --------------------------------------------------
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO user_faces
                (employee_id, picture_url, created_at)
            VALUES
                (?, ?, datetime('now'))
            """,
            (
                employee_no,
                f"/users/faces/{filename}",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_users_full(include_inactive=False):
    """
    Returns users for Users management page.
    Excludes visitors by design.
    """

    conn = get_conn()
    cur = conn.cursor()

    sql = """
        SELECT
            u.id,
            u.employee_id,
            u.name,
            u.active,
            d.name AS device_name,
            COUNT(uf.id) AS face_count
        FROM users u
        LEFT JOIN device_users du
            ON du.user_id = u.id
        LEFT JOIN devices d
            ON d.id = du.device_id
        LEFT JOIN user_faces uf
            ON uf.employee_id = u.employee_id
        WHERE COALESCE(u.is_visitor, 0) = 0
    """

    params = []

    if not include_inactive:
        sql += " AND u.active = 1"

    sql += """
        GROUP BY u.id
        ORDER BY
            CASE
                WHEN u.employee_id GLOB '[0-9]*'
                THEN CAST(u.employee_id AS INTEGER)
                ELSE 999999999
            END,
            u.employee_id
    """

    rows = cur.execute(sql, params).fetchall()
    conn.close()
    return rows
