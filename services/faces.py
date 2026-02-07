import os
import requests
from requests.auth import HTTPDigestAuth

FACES_DIR = "/opt/attendance/faces"

class FacePushError(Exception):
    pass


def _ensure_face_file(employee_id):
    path = os.path.join(FACES_DIR, f"{employee_id}.jpg")
    if not os.path.isfile(path):
        raise FacePushError(f"Face file not found: {path}")
    return path


def create_face_record(device_ip, username, password, employee_id):
    """
    Creates a face record (metadata) on the device.
    Returns FPID if provided by device, otherwise None.
    """
    url = f"http://{device_ip}/ISAPI/Intelligent/FDLib/FDSetUp?format=json"

    payload = {
        "faceLibType": "blackFD",
        "FDID": "1",
        "FPID": "AUTO",
        "employeeNo": str(employee_id)
    }

    r = requests.post(
        url,
        json=payload,
        auth=HTTPDigestAuth(username, password),
        timeout=10
    )

    r.raise_for_status()
    data = r.json()

    # Some firmwares return FPID, others do not.
    return data.get("FPID")


def upload_face_image(device_ip, username, password, fpid, image_path):
    """
    Uploads the JPEG image to the previously created FPID.
    """
    if not fpid:
        raise FacePushError("FPID missing; cannot upload image")

    url = f"http://{device_ip}/ISAPI/Intelligent/FDLib/FacePic/{fpid}?format=json"

    with open(image_path, "rb") as fh:
        r = requests.put(
            url,
            data=fh,
            headers={"Content-Type": "image/jpeg"},
            auth=HTTPDigestAuth(username, password),
            timeout=20
        )

    r.raise_for_status()
    return True


def push_face_to_device(device_ip, username, password, employee_id):
    """
    High-level, idempotent face push.
    """
    image_path = _ensure_face_file(employee_id)

    fpid = create_face_record(
        device_ip=device_ip,
        username=username,
        password=password,
        employee_id=employee_id
    )

    upload_face_image(
        device_ip=device_ip,
        username=username,
        password=password,
        fpid=fpid,
        image_path=image_path
    )

    return True
