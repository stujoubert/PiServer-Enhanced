# routes/misc.py
from flask import Blueprint, jsonify, session, request, redirect, url_for
from translations import LANG

bp = Blueprint("misc", __name__)

@bp.route("/set-language")
def set_language():
    lang = request.args.get("lang", "en")
    if lang not in LANG:
        lang = "en"
    session["lang"] = lang
    return redirect(request.referrer or url_for("daily.daily"))

@bp.route("/health")
def health():
    return jsonify({"status": "ok"})
