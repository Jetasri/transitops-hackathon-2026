"""
TransitOps — Driver Management Blueprint
=========================================
Owns: /drivers/* routes.

Do NOT redefine models here — always import from app.models.
"""

from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.models import Driver

drivers_bp = Blueprint("drivers_bp", __name__, url_prefix="/drivers")


def _parse_date(value):
    """Parse an <input type="date"> value (YYYY-MM-DD) into a date object."""
    return datetime.strptime(value, "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------
@drivers_bp.route("/", methods=["GET"])
@login_required
def list_drivers():
    query = Driver.query

    status_filter = request.args.get("status", "").strip()
    if status_filter:
        query = query.filter(Driver.status == status_filter)

    drivers = query.order_by(Driver.name.asc()).all()

    return render_template(
        "drivers/list.html",
        drivers=drivers,
        statuses=Driver.VALID_STATUSES,
        selected_status=status_filter,
    )


# ---------------------------------------------------------------------------
# DETAIL
# ---------------------------------------------------------------------------
@drivers_bp.route("/<int:driver_id>", methods=["GET"])
@login_required
def driver_detail(driver_id):
    driver = Driver.query.get_or_404(driver_id)
    return render_template("drivers/detail.html", driver=driver)


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------
@drivers_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_driver():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        license_number = request.form.get("license_number", "").strip()
        license_category = request.form.get("license_category", "").strip() or None
        contact_number = request.form.get("contact_number", "").strip() or None
        status = request.form.get("status", "Available")

        error = None
        license_expiry = None
        safety_score = 100.0

        if not name or not license_number or not request.form.get("license_expiry"):
            error = "Name, license number, and license expiry are required."
        else:
            try:
                license_expiry = _parse_date(request.form["license_expiry"])
            except ValueError:
                error = "License expiry must be a valid date."

        if not error:
            raw_score = request.form.get("safety_score", "100")
            try:
                safety_score = float(raw_score) if raw_score else 100.0
            except ValueError:
                error = "Safety score must be a number."

        if not error and Driver.query.filter_by(license_number=license_number).first():
            error = f"A driver with license number '{license_number}' already exists."

        if not error and status not in Driver.VALID_STATUSES:
            error = "Invalid status selected."

        if error:
            flash(error, "danger")
            return render_template(
                "drivers/form.html",
                driver=None,
                statuses=Driver.VALID_STATUSES,
                form_data=request.form,
            )

        driver = Driver(
            name=name,
            license_number=license_number,
            license_category=license_category,
            license_expiry=license_expiry,
            contact_number=contact_number,
            safety_score=safety_score,
            status=status,
        )
        db.session.add(driver)
        db.session.commit()
        flash(f"Driver {driver.name} created.", "success")
        return redirect(url_for("drivers_bp.driver_detail", driver_id=driver.id))

    return render_template(
        "drivers/form.html", driver=None, statuses=Driver.VALID_STATUSES, form_data={}
    )


# ---------------------------------------------------------------------------
# EDIT
# ---------------------------------------------------------------------------
@drivers_bp.route("/<int:driver_id>/edit", methods=["GET", "POST"])
@login_required
def edit_driver(driver_id):
    driver = Driver.query.get_or_404(driver_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        license_number = request.form.get("license_number", "").strip()
        license_category = request.form.get("license_category", "").strip() or None
        contact_number = request.form.get("contact_number", "").strip() or None
        status = request.form.get("status", driver.status)

        error = None
        license_expiry = driver.license_expiry
        safety_score = driver.safety_score

        if not name or not license_number or not request.form.get("license_expiry"):
            error = "Name, license number, and license expiry are required."
        else:
            try:
                license_expiry = _parse_date(request.form["license_expiry"])
            except ValueError:
                error = "License expiry must be a valid date."

        if not error:
            raw_score = request.form.get("safety_score", "")
            try:
                safety_score = float(raw_score) if raw_score else driver.safety_score
            except ValueError:
                error = "Safety score must be a number."

        if not error:
            duplicate = Driver.query.filter(
                Driver.license_number == license_number, Driver.id != driver.id
            ).first()
            if duplicate:
                error = f"A driver with license number '{license_number}' already exists."

        if not error and status not in Driver.VALID_STATUSES:
            error = "Invalid status selected."

        if error:
            flash(error, "danger")
            return render_template(
                "drivers/form.html",
                driver=driver,
                statuses=Driver.VALID_STATUSES,
                form_data=request.form,
            )

        driver.name = name
        driver.license_number = license_number
        driver.license_category = license_category
        driver.license_expiry = license_expiry
        driver.contact_number = contact_number
        driver.safety_score = safety_score
        driver.status = status
        db.session.commit()
        flash(f"Driver {driver.name} updated.", "success")
        return redirect(url_for("drivers_bp.driver_detail", driver_id=driver.id))

    return render_template(
        "drivers/form.html",
        driver=driver,
        statuses=Driver.VALID_STATUSES,
        form_data=None,
    )


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------
@drivers_bp.route("/<int:driver_id>/delete", methods=["POST"])
@login_required
def delete_driver(driver_id):
    driver = Driver.query.get_or_404(driver_id)

    if driver.trips:
        flash(
            f"Cannot delete {driver.name}: they have trip history. "
            "Set their status to 'Off Duty' or 'Suspended' instead.",
            "danger",
        )
        return redirect(url_for("drivers_bp.driver_detail", driver_id=driver.id))

    db.session.delete(driver)
    db.session.commit()
    flash("Driver deleted.", "success")
    return redirect(url_for("drivers_bp.list_drivers"))
