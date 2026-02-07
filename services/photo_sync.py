import os
import requests
from typing import Optional

PHOTO_DIR = "/var/lib/attendance/photos"


def ensure_photo_dir():
    os.makedirs(PHOTO_DIR, exist_ok=True)


def download_employee_photo(
    device_ip: str,
    username: str,
    password: str,
    employee_id: str,
    timeout: int = 10,
) -> Optional[str]:
    """
    Downloads employee face photo from Hikvision device.

    Returns local file path if successful, else None.
    """
    ensure_photo_dir()

    url = (
        f"https://{device_ip}/ISAPI/Intelligent/FDLib/FDSearch"
    )

    payload = f"""
    <FDSearchDescription>
        <searchID>{employee_id}</searchID>
        <maxResults>1</maxResults>
        <FDID>1</FDID>
        <faceLibType>blackFD</faceLibType>
        <searchResultPosition>0</searchResultPosition>
    </FDSearchDescription>
    """

    try:
        r = requests.post(
            url,
            data=payload,
            auth=(username, password),
            verify=False,
            timeout=timeout,
            headers={"Content-Type": "application/xml"},
        )
    except Exception:
        return None

    if r.status_code != 200:
        return None

    # Hikvision returns binary image data in some models
    photo_path = os.path.join(PHOTO_DIR, f"{employee_id}.jpg")

    try:
        with open(photo_path, "wb") as f:
            f.write(r.content)
    except Exception:
        return None

    return photo_path


def bulk_download_photos(
    device_ip: str,
    username: str,
    password: str,
    employee_ids: list[str],
):
    results = {}

    for emp_id in employee_ids:
        path = download_employee_photo(
            device_ip,
            username,
            password,
            emp_id,
        )
        results[emp_id] = bool(path)

    return results
