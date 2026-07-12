"""
TransitOps — Trip Management Blueprint
========================================
Owns: /trips/*

Business rules enforced here (see inline comments):
  - new_trip only offers dispatchable vehicles / assignable drivers, and
    re-validates both on submit (never trust client input).
  - cargo_weight_kg must not exceed the selected vehicle's max_load_kg.
  - dispatch_trip flips trip + vehicle + driver status together, one commit.
  - complete_trip flips trip + vehicle + driver status together, one commit,
    and pushes the final odometer reading onto the vehicle.
  - cancel_trip is only allowed from "Dispatched" and restores vehicle/driver.

Every state-changing route wraps its writes in try/except and rolls back on
failure so nothing is ever half-saved, and reports problems via flash +
redirect rather than raising.
"""

from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.models import Trip, Vehicle, Driver
from app.auth import role_required

trips_bp = Blueprint("trips_bp", __name__, url_prefix="/trips")


# ---------------------------------------------------------------------------
# LIST
# ---------------------------------------------------------------------------
@trips_bp.route("/")
@login_required
def list_trips():
    status_filter = request.args.get("status", "").strip()

    query = Trip.query
    if status_filter and status_filter in Trip.VALID_STATUSES:
        query = query.filter_by(status=status_filter)

    trips = query.order_by(Trip.created_at.desc()).all()

    return render_template(
        "trips/list.html",
        trips=trips,
        statuses=Trip.VALID_STATUSES,
        current_status=status_filter,
    )


# ---------------------------------------------------------------------------
# DETAIL
# ---------------------------------------------------------------------------
@trips_bp.route("/<int:id>")
@login_required
def trip_detail(id):
    trip = Trip.query.get_or_404(id)
    return render_template("trips/detail.html", trip=trip)


# ---------------------------------------------------------------------------
# NEW
# ---------------------------------------------------------------------------
@trips_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("fleet_manager", "driver")
def new_trip():
    # Server-side source of truth for the dropdowns — never trust the client.
    available_vehicles = [v for v in Vehicle.query.all() if v.is_dispatchable()]
    available_drivers = [d for d in Driver.query.all() if d.is_assignable()]

    if request.method == "POST":
        source = (request.form.get("source") or "").strip()
        destination = (request.form.get("destination") or "").strip()
        vehicle_id = request.form.get("vehicle_id", type=int)
        driver_id = request.form.get("driver_id", type=int)
        cargo_weight_kg = request.form.get("cargo_weight_kg", type=float)
        planned_distance_km = request.form.get("planned_distance_km", type=float)

        if not source or not destination:
            flash("Source and destination are required.", "danger")
            return redirect(url_for("trips_bp.new_trip"))

        if vehicle_id is None or driver_id is None:
            flash("Please select a vehicle and a driver.", "danger")
            return redirect(url_for("trips_bp.new_trip"))

        if cargo_weight_kg is None or planned_distance_km is None:
            flash("Cargo weight and planned distance are required.", "danger")
            return redirect(url_for("trips_bp.new_trip"))

        if cargo_weight_kg <= 0 or planned_distance_km <= 0:
            flash("Cargo weight and planned distance must be positive numbers.", "danger")
            return redirect(url_for("trips_bp.new_trip"))

        # Re-validate on submit — the dropdown could be stale by the time the
        # form is posted (another user may have dispatched/suspended it).
        vehicle = Vehicle.query.get(vehicle_id)
        driver = Driver.query.get(driver_id)

        if not vehicle or not vehicle.is_dispatchable():
            flash("Selected vehicle is no longer available for dispatch.", "danger")
            return redirect(url_for("trips_bp.new_trip"))

        if not driver or not driver.is_assignable():
            flash("Selected driver is no longer available for assignment.", "danger")
            return redirect(url_for("trips_bp.new_trip"))

        if cargo_weight_kg > vehicle.max_load_kg:
            flash(
                f"Cargo weight ({cargo_weight_kg} kg) exceeds this vehicle's "
                f"max load ({vehicle.max_load_kg} kg).",
                "danger",
            )
            return redirect(url_for("trips_bp.new_trip"))

        trip = Trip(
            source=source,
            destination=destination,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            cargo_weight_kg=cargo_weight_kg,
            planned_distance_km=planned_distance_km,
            status="Draft",
        )

        try:
            db.session.add(trip)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Something went wrong creating the trip. Please try again.", "danger")
            return redirect(url_for("trips_bp.new_trip"))

        flash("Trip created as Draft.", "success")
        return redirect(url_for("trips_bp.trip_detail", id=trip.id))

    return render_template(
        "trips/new.html", vehicles=available_vehicles, drivers=available_drivers
    )


# ---------------------------------------------------------------------------
# DISPATCH
# ---------------------------------------------------------------------------
@trips_bp.route("/<int:id>/dispatch", methods=["POST"])
@login_required
@role_required("fleet_manager", "driver")
def dispatch_trip(id):
    trip = Trip.query.get_or_404(id)

    if trip.status != "Draft":
        flash("Only Draft trips can be dispatched.", "danger")
        return redirect(url_for("trips_bp.trip_detail", id=id))

    vehicle = trip.vehicle
    driver = trip.driver

    if not vehicle.is_dispatchable():
        flash("Vehicle is no longer available for dispatch.", "danger")
        return redirect(url_for("trips_bp.trip_detail", id=id))

    if not driver.is_assignable():
        flash("Driver is no longer available for assignment.", "danger")
        return redirect(url_for("trips_bp.trip_detail", id=id))

    try:
        trip.status = "Dispatched"
        trip.dispatched_at = datetime.utcnow()
        vehicle.status = "On Trip"
        driver.status = "On Trip"
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Failed to dispatch trip — nothing was changed.", "danger")
        return redirect(url_for("trips_bp.trip_detail", id=id))

    flash("Trip dispatched.", "success")
    return redirect(url_for("trips_bp.trip_detail", id=id))


# ---------------------------------------------------------------------------
# COMPLETE
# ---------------------------------------------------------------------------
@trips_bp.route("/<int:id>/complete", methods=["POST"])
@login_required
@role_required("fleet_manager", "driver")
def complete_trip(id):
    trip = Trip.query.get_or_404(id)

    if trip.status != "Dispatched":
        flash("Only Dispatched trips can be completed.", "danger")
        return redirect(url_for("trips_bp.trip_detail", id=id))

    final_odometer = request.form.get("final_odometer", type=float)
    fuel_consumed_l = request.form.get("fuel_consumed_l", type=float)

    if final_odometer is None or fuel_consumed_l is None:
        flash("Final odometer and fuel consumed are both required.", "danger")
        return redirect(url_for("trips_bp.trip_detail", id=id))

    vehicle = trip.vehicle
    driver = trip.driver

    if final_odometer < vehicle.odometer:
        flash("Final odometer cannot be less than the vehicle's current odometer.", "danger")
        return redirect(url_for("trips_bp.trip_detail", id=id))

    if fuel_consumed_l < 0:
        flash("Fuel consumed cannot be negative.", "danger")
        return redirect(url_for("trips_bp.trip_detail", id=id))

    try:
        trip.status = "Completed"
        trip.completed_at = datetime.utcnow()
        trip.final_odometer = final_odometer
        trip.fuel_consumed_l = fuel_consumed_l
        vehicle.odometer = final_odometer
        vehicle.status = "Available"
        driver.status = "Available"
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Failed to complete trip — nothing was changed.", "danger")
        return redirect(url_for("trips_bp.trip_detail", id=id))

    flash("Trip completed.", "success")
    return redirect(url_for("trips_bp.trip_detail", id=id))


# ---------------------------------------------------------------------------
# CANCEL
# ---------------------------------------------------------------------------
@trips_bp.route("/<int:id>/cancel", methods=["POST"])
@login_required
@role_required("fleet_manager", "driver")
def cancel_trip(id):
    trip = Trip.query.get_or_404(id)

    if trip.status != "Dispatched":
        flash("Only Dispatched trips can be cancelled.", "danger")
        return redirect(url_for("trips_bp.trip_detail", id=id))

    vehicle = trip.vehicle
    driver = trip.driver

    try:
        trip.status = "Cancelled"
        vehicle.status = "Available"
        driver.status = "Available"
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Failed to cancel trip — nothing was changed.", "danger")
        return redirect(url_for("trips_bp.trip_detail", id=id))

    flash("Trip cancelled.", "warning")
    return redirect(url_for("trips_bp.trip_detail", id=id))
