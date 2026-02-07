import os
import requests
from requests.auth import HTTPDigestAuth

PHOTO_DIR = "/var/lib/attendance/photos"

def ensure_photo_dir():
    os.makedirs(PHOTO_DIR, exist_ok=True)

def download_user_photo(
    device_ip: str,
    username: str,
    password: str,
    employee_id: str,
    verify_ssl: bool = False,
    timeout: int = 10,
) -> bool:
    """
    Downloads and stores user photo from Hikvision device.
    Returns True if downloaded, False otherwise.
    """

    ensure_photo_dir()

    url = f"https://{device_ip}/ISAPI/AccessControl/UserInfo/Download"
    params = {"employeeNo": employee_id}

    try:
        r = requests.get(
            url,
            params=params,
            auth=HTTPDigestAuth(username, password),
            verify=verify_ssl,
            timeout=timeout,
        )

        if r.status_code != 200 or not r.content:
            return False

        path = os.path.join(PHOTO_DIR, f"{employee_id}.jpg")
        with open(path, "wb") as f:
            f.write(r.content)

        return True

    except Exception:
        return False
