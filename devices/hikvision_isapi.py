import requests
from requests.auth import HTTPDigestAuth
from datetime import datetime, timedelta

class HikvisionISAPI:
    def __init__(self, ip, username, password, timeout=10):
        self.base = f"http://{ip}/ISAPI"
        self.auth = HTTPDigestAuth(username, password)
        self.timeout = timeout

    # -----------------------------
    # Create / Update user
    # -----------------------------
    def create_or_update_user(self, employee_no: str, name: str):
        url = f"{self.base}/AccessControl/UserInfo/SetUp?format=json"

        payload = {
            "UserInfo": {
                "employeeNo": str(employee_no),
                "name": name,
                "userType": "normal",
                "Valid": {
                    "enable": True,
                    "beginTime": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    "endTime": (datetime.now() + timedelta(days=365 * 5)).strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeType": "local",
                },
                "doorRight": "1",
                "RightPlan": [
                    {
                        "doorNo": "1",
                        "planTemplateNo": "1",
                    }
                ],
            }
        }

        r = requests.put(
            url,
            json=payload,
            auth=self.auth,
            timeout=self.timeout,
        )

        if r.status_code != 200:
            raise RuntimeError(f"User create failed ({r.status_code}): {r.text}")

        return True

    # -----------------------------
    # Upload face (FDLib)
    # -----------------------------
    def upload_face(self, employee_no: str, image_bytes: bytes):
        url = f"{self.base}/Intelligent/FDLib/FDSetUp?format=json"

        files = {
            "FaceDataRecord": (
                None,
                f"""
                {{
                    "FaceDataRecord": {{
                        "employeeNo": "{employee_no}",
                        "faceLibType": "blackFD",
                        "FDID": "1"
                    }}
                }}
                """,
                "application/json",
            ),
            "img": ("face.jpg", image_bytes, "image/jpeg"),
        }

        r = requests.post(
            url,
            files=files,
            auth=self.auth,
            timeout=self.timeout,
        )

        if r.status_code != 200:
            raise RuntimeError(f"Face upload failed ({r.status_code}): {r.text}")

        return True
