# services/settings.py
from db import get_conn
from pathlib import Path
from PIL import Image

UPLOAD_DIR = Path("static/uploads")
LOGO_NAME = "company_logo.png"


def get_company_settings():
    conn = get_conn()
    rows = conn.execute(
        "SELECT key, value FROM settings WHERE key LIKE 'company_%'"
    ).fetchall()
    conn.close()

    data = {r["key"]: r["value"] for r in rows}

    return {
        "name": data.get("company_name", ""),
        "rfc": data.get("company_rfc", ""),
        "logo_url": f"/static/uploads/{LOGO_NAME}"
        if (UPLOAD_DIR / LOGO_NAME).exists()
        else None,
    }


def save_company_settings(name, rfc, logo_file=None):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)",
        ("company_name", name),
    )
    cur.execute(
        "INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)",
        ("company_rfc", rfc),
    )

    conn.commit()
    conn.close()

    if logo_file:
        _save_logo(logo_file)


def _save_logo(file_storage):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    img = Image.open(file_storage.stream)
    img = img.convert("RGBA")

    max_height = 80
    if img.height > max_height:
        ratio = max_height / img.height
        img = img.resize(
            (int(img.width * ratio), max_height),
            Image.LANCZOS,
        )

    img.save(UPLOAD_DIR / LOGO_NAME, format="PNG", optimize=True)
