"""
TransitOps — Maintenance Blueprint
====================================
Owns: /maintenance/*

Business rules enforced here:
  - Opening a new Active maintenance record immediately pushes the linked
    vehicle to "In Shop" — trip creation/dispatch already refuses vehicles
    that aren't Available, so this keeps that invariant in sync.
  - You can't open maintenance against a Retired vehicle, or one currently
    On Trip.
  - Closing a record restores the vehicle to "Available", UNLESS the vehicle
    has since been marked "Retired" (e.g. by another workflow) — in which
    case it stays Retired.

Every state-changing route commits vehicle + log together, and rolls back
on any failure so nothing is left half-saved.
"""

from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.models import MaintenanceLog, Vehicle
from app.auth import role_required

maintenance_bp = Blueprint("maintenance_bp", __name__, url_prefix="/maintenance")


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------
@maintenance_bp.route("/")
@login_required
def list_maintenance():
    status_filter = request.args.get("status", "").strip()

    query = MaintenanceLog.query
    if status_filter and status_filter in MaintenanceLog.VALID_STATUSES:
        query = query.filter_by(status=status_filter)

    logs = query.order_by(MaintenanceLog.created_at.desc()).all()

    return render_template(
        "maintenance/list.html",
        logs=logs,
        statuses=MaintenanceLog.VALID_STATUSES,
        current_status=status_filter,
    )


# ---------------------------------------------------------------------------
# NEW
# ---------------------------------------------------------------------------
@maintenance_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("fleet_manager", "safety_officer")
def new_maintenance():
    # Retired vehicles never need new maintenance; On Trip / In Shop vehicles
    # are still shown as context but re-validated on submit below.
    vehicles = (
        Vehicle.query.filter(Vehicle.status != "Retired")
        .order_by(Vehicle.reg_number)
        .all()
    )

    if request.method == "POST":
        vehicle_id = request.form.get("vehicle_id", type=int)
        description = (request.form.get("description") or "").strip()
        cost = request.form.get("cost", type=float)

        if vehicle_id is None or not description:
            flash("Vehicle and description are required.", "danger")
            return redirect(url_for("maintenance_bp.new_maintenance"))

        vehicle = Vehicle.query.get(vehicle_id)
        if not vehicle:
            flash("Selected vehicle does not exist.", "danger")
            return redirect(url_for("maintenance_bp.new_maintenance"))

        if vehicle.status == "Retired":
            flash("Cannot open a maintenance record for a retired vehicle.", "danger")
            return redirect(url_for("maintenance_bp.new_maintenance"))

        if vehicle.status == "On Trip":
            flash("Cannot open a maintenance record for a vehicle currently on a trip.", "danger")
            return redirect(url_for("maintenance_bp.new_maintenance"))

        if cost is not None and cost < 0:
            flash("Cost cannot be negative.", "danger")
            return redirect(url_for("maintenance_bp.new_maintenance"))

        log = MaintenanceLog(
            vehicle_id=vehicle.id,
            description=description,
            cost=cost or 0,
            status="Active",
        )

        try:
            db.session.add(log)
            vehicle.status = "In Shop"
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Failed to create the maintenance record. Please try again.", "danger")
            return redirect(url_for("maintenance_bp.new_maintenance"))

        flash("Maintenance record opened; vehicle marked In Shop.", "success")
        return redirect(url_for("maintenance_bp.list_maintenance"))

    return render_template("maintenance/new.html", vehicles=vehicles)


# ---------------------------------------------------------------------------
# CLOSE
# ---------------------------------------------------------------------------
@maintenance_bp.route("/<int:id>/close", methods=["POST"])
@login_required
@role_required("fleet_manager", "safety_officer")
def close_maintenance(id):
    log = MaintenanceLog.query.get_or_404(id)

    if log.status != "Active":
        flash("Only Active maintenance records can be closed.", "danger")
        return redirect(url_for("maintenance_bp.list_maintenance"))

    vehicle = log.vehicle

    try:
        log.status = "Closed"
        log.closed_at = datetime.utcnow()
        if vehicle.status != "Retired":
            vehicle.status = "Available"
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Failed to close the maintenance record.", "danger")
        return redirect(url_for("maintenance_bp.list_maintenance"))

    flash("Maintenance record closed.", "success")
    return redirect(url_for("maintenance_bp.list_maintenance"))
