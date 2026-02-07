import os
from flask import Blueprint, send_from_directory, abort

PHOTO_DIR = "/var/lib/attendance/photos"

bp = Blueprint("photos", __name__)

@bp.route("/photos/<employee_id>.jpg")
def employee_photo(employee_id):
    filename = f"{employee_id}.jpg"
    path = os.path.join(PHOTO_DIR, filename)

    if not os.path.exists(path):
        abort(404)

    return send_from_directory(PHOTO_DIR, filename)
