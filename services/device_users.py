from flask import Blueprint, render_template, request, flash
from authz import login_required, role_required
from services.device_push import push_users_to_device
from services.user_helpers import list_users
from db import get_conn

bp = Blueprint("device_users", __name__, url_prefix="/devices/users")

def isapi_user_exists(base_url: str, username: str, password: str, employee_no: str) -> bool:
    url = f"{base_url}/ISAPI/AccessControl/UserInfo/Search?format=json"
    payload = {
        "UserInfoSearchCond": {
            "searchID": "1",
            "searchResultPosition": 0,
            "maxResults": 1,
            "EmployeeNoList": [{"employeeNo": str(employee_no)}],
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
        cond = data.get("UserInfoSearch", {}) or data.get("UserInfoSearchResult", {}) or data
        matches = cond.get("numOfMatches") or cond.get("NumOfMatches") or 0
        # Some firmwares return "UserInfo" directly when maxResults=1
        if matches:
            return int(matches) > 0
        ui = cond.get("UserInfo")
        if isinstance(ui, dict):
            return str(ui.get("employeeNo", "")) == str(employee_no)
        if isinstance(ui, list):
            return any(str(x.get("employeeNo", "")) == str(employee_no) for x in ui if isinstance(x, dict))
        return False
    except Exception:
        return False


@bp.route("/", methods=["GET", "POST"])
@login_required
@role_required("admin")
def push_users():
    conn = get_conn()
    devices = conn.execute("SELECT id, name FROM devices").fetchall()
    conn.close()

    if request.method == "POST":
        device_id = int(request.form["device_id"])
        user_ids = request.form.getlist("user_ids[]")

        results = push_users_to_device(device_id, user_ids)
        return render_template(
            "device_user_push.html",
            devices=devices,
            users=list_users(),
            results=results,
        )

    return render_template(
        "device_user_push.html",
        devices=devices,
        users=list_users(),
        results=None,
    )
