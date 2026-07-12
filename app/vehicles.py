"""
TransitOps — Vehicle Registry Blueprint
========================================
Owns: /vehicles/* routes.

Do NOT redefine models here — always import from app.models.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.models import Vehicle, Driver

vehicles_bp = Blueprint("vehicles_bp", __name__, url_prefix="/vehicles")


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------
@vehicles_bp.route("/", methods=["GET"])
@login_required
def list_vehicles():
    query = Vehicle.query

    type_filter = request.args.get("type", "").strip()
    status_filter = request.args.get("status", "").strip()
    region_filter = request.args.get("region", "").strip()

    if type_filter:
        query = query.filter(Vehicle.type == type_filter)
    if status_filter:
        query = query.filter(Vehicle.status == status_filter)
    if region_filter:
        query = query.filter(Vehicle.region == region_filter)

    vehicles = query.order_by(Vehicle.reg_number.asc()).all()

    # Populate filter dropdown options from what's actually in the DB.
    all_types = sorted({v.type for v in Vehicle.query.all() if v.type})
    all_regions = sorted({v.region for v in Vehicle.query.all() if v.region})

    return render_template(
        "vehicles/list.html",
        vehicles=vehicles,
        statuses=Vehicle.VALID_STATUSES,
        all_types=all_types,
        all_regions=all_regions,
        selected_type=type_filter,
        selected_status=status_filter,
        selected_region=region_filter,
    )


# ---------------------------------------------------------------------------
# DETAIL
# ---------------------------------------------------------------------------
@vehicles_bp.route("/<int:vehicle_id>", methods=["GET"])
@login_required
def vehicle_detail(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)
    return render_template("vehicles/detail.html", vehicle=vehicle)


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------
@vehicles_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_vehicle():
    if request.method == "POST":
        reg_number = request.form.get("reg_number", "").strip()
        name = request.form.get("name", "").strip()
        vtype = request.form.get("type", "").strip()
        region = request.form.get("region", "").strip() or None
        status = request.form.get("status", "Available")

        error = None
        max_load_kg = None
        odometer = 0.0
        acquisition_cost = 0.0

        if not reg_number or not name or not vtype:
            error = "Registration number, name, and type are required."
        else:
            try:
                max_load_kg = float(request.form.get("max_load_kg", "0") or 0)
                odometer = float(request.form.get("odometer", "0") or 0)
                acquisition_cost = float(request.form.get("acquisition_cost", "0") or 0)
            except ValueError:
                error = "Load capacity, odometer, and cost must be numbers."

        if not error and Vehicle.query.filter_by(reg_number=reg_number).first():
            error = f"A vehicle with reg number '{reg_number}' already exists."

        if not error and status not in Vehicle.VALID_STATUSES:
            error = "Invalid status selected."

        if error:
            flash(error, "danger")
            return render_template(
                "vehicles/form.html",
                vehicle=None,
                statuses=Vehicle.VALID_STATUSES,
                form_data=request.form,
            )

        vehicle = Vehicle(
            reg_number=reg_number,
            name=name,
            type=vtype,
            max_load_kg=max_load_kg,
            odometer=odometer,
            acquisition_cost=acquisition_cost,
            region=region,
            status=status,
        )
        db.session.add(vehicle)
        db.session.commit()
        flash(f"Vehicle {vehicle.reg_number} created.", "success")
        return redirect(url_for("vehicles_bp.vehicle_detail", vehicle_id=vehicle.id))

    return render_template(
        "vehicles/form.html", vehicle=None, statuses=Vehicle.VALID_STATUSES, form_data={}
    )


# ---------------------------------------------------------------------------
# EDIT
# ---------------------------------------------------------------------------
@vehicles_bp.route("/<int:vehicle_id>/edit", methods=["GET", "POST"])
@login_required
def edit_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    if request.method == "POST":
        reg_number = request.form.get("reg_number", "").strip()
        name = request.form.get("name", "").strip()
        vtype = request.form.get("type", "").strip()
        region = request.form.get("region", "").strip() or None
        status = request.form.get("status", vehicle.status)

        error = None
        max_load_kg = vehicle.max_load_kg
        odometer = vehicle.odometer
        acquisition_cost = vehicle.acquisition_cost

        if not reg_number or not name or not vtype:
            error = "Registration number, name, and type are required."
        else:
            try:
                max_load_kg = float(request.form.get("max_load_kg", "0") or 0)
                odometer = float(request.form.get("odometer", "0") or 0)
                acquisition_cost = float(request.form.get("acquisition_cost", "0") or 0)
            except ValueError:
                error = "Load capacity, odometer, and cost must be numbers."

        if not error:
            duplicate = Vehicle.query.filter(
                Vehicle.reg_number == reg_number, Vehicle.id != vehicle.id
            ).first()
            if duplicate:
                error = f"A vehicle with reg number '{reg_number}' already exists."

        if not error and status not in Vehicle.VALID_STATUSES:
            error = "Invalid status selected."

        if error:
            flash(error, "danger")
            return render_template(
                "vehicles/form.html",
                vehicle=vehicle,
                statuses=Vehicle.VALID_STATUSES,
                form_data=request.form,
            )

        vehicle.reg_number = reg_number
        vehicle.name = name
        vehicle.type = vtype
        vehicle.max_load_kg = max_load_kg
        vehicle.odometer = odometer
        vehicle.acquisition_cost = acquisition_cost
        vehicle.region = region
        vehicle.status = status
        db.session.commit()
        flash(f"Vehicle {vehicle.reg_number} updated.", "success")
        return redirect(url_for("vehicles_bp.vehicle_detail", vehicle_id=vehicle.id))

    return render_template(
        "vehicles/form.html",
        vehicle=vehicle,
        statuses=Vehicle.VALID_STATUSES,
        form_data=None,
    )


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------
@vehicles_bp.route("/<int:vehicle_id>/delete", methods=["POST"])
@login_required
def delete_vehicle(vehicle_id):
    vehicle = Vehicle.query.get_or_404(vehicle_id)

    if vehicle.trips or vehicle.maintenance_logs:
        flash(
            f"Cannot delete {vehicle.reg_number}: it has trip or maintenance "
            "history. Retire it instead by setting its status to 'Retired'.",
            "danger",
        )
        return redirect(url_for("vehicles_bp.vehicle_detail", vehicle_id=vehicle.id))

    db.session.delete(vehicle)
    db.session.commit()
    flash("Vehicle deleted.", "success")
    return redirect(url_for("vehicles_bp.list_vehicles"))
