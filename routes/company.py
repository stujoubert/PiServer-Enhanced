from flask import Blueprint, render_template, request, redirect, url_for, flash

from authz import login_required, role_required
from services.settings import get_company_settings, save_company_settings

bp = Blueprint("company", __name__, url_prefix="/company")


@bp.route("/", methods=["GET", "POST"])
@login_required
@role_required("admin")
def company_settings():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        rfc = request.form.get("rfc", "").strip()
        logo_file = request.files.get("logo")

        if not name:
            flash("Company name is required.", "danger")
            return redirect(url_for("company.company_settings"))

        if not rfc:
            flash("RFC is required.", "danger")
            return redirect(url_for("company.company_settings"))

        save_company_settings(
            name=name,
            rfc=rfc,
            logo_file=logo_file,
        )

        flash("Company settings saved successfully.", "success")
        return redirect(url_for("company.company_settings"))

    # GET
    data = get_company_settings()
    return render_template("company.html", data=data)
