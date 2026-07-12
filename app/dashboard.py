"""
Dashboard Blueprint
====================
Home page ("/") showing fleet-wide KPI cards. Supports optional
query-param filters (vehicle type, status, region) which re-run the
vehicle-related counts against the filtered subset.
"""

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models import Vehicle, Driver, Trip

dashboard_bp = Blueprint("dashboard_bp", __name__, url_prefix="")


@dashboard_bp.route("/", methods=["GET"])
@login_required
def index():
    # ---- optional filters (vehicle type / status / region) ----
    veh_type = request.args.get("type") or None
    veh_status = request.args.get("status") or None
    veh_region = request.args.get("region") or None

    vehicle_query = Vehicle.query
    if veh_type:
        vehicle_query = vehicle_query.filter(Vehicle.type == veh_type)
    if veh_status:
        vehicle_query = vehicle_query.filter(Vehicle.status == veh_status)
    if veh_region:
        vehicle_query = vehicle_query.filter(Vehicle.region == veh_region)

    filtered_vehicles = vehicle_query.all()

    # ---- vehicle KPIs (respect filters) ----
    active_vehicles = sum(1 for v in filtered_vehicles if v.status != "Retired")
    available_vehicles = sum(1 for v in filtered_vehicles if v.status == "Available")
    vehicles_in_maintenance = sum(1 for v in filtered_vehicles if v.status == "In Shop")
    on_trip_vehicles = sum(1 for v in filtered_vehicles if v.status == "On Trip")

    fleet_utilization_pct = (
        round((on_trip_vehicles / active_vehicles) * 100, 1)
        if active_vehicles
        else 0.0
    )

    # ---- trip / driver KPIs (fleet-wide, not affected by vehicle filters) ----
    active_trips = Trip.query.filter(Trip.status == "Dispatched").count()
    pending_trips = Trip.query.filter(Trip.status == "Draft").count()
    drivers_on_duty = Driver.query.filter(Driver.status == "On Trip").count()

    # ---- filter dropdown options (unfiltered, so options never disappear) ----
    vehicle_types = sorted({v.type for v in Vehicle.query.all() if v.type})
    vehicle_statuses = list(Vehicle.VALID_STATUSES)
    vehicle_regions = sorted({v.region for v in Vehicle.query.all() if v.region})

    return render_template(
        "dashboard/index.html",
        active_vehicles=active_vehicles,
        available_vehicles=available_vehicles,
        vehicles_in_maintenance=vehicles_in_maintenance,
        active_trips=active_trips,
        pending_trips=pending_trips,
        drivers_on_duty=drivers_on_duty,
        fleet_utilization_pct=fleet_utilization_pct,
        vehicle_types=vehicle_types,
        vehicle_statuses=vehicle_statuses,
        vehicle_regions=vehicle_regions,
        selected_type=veh_type,
        selected_status=veh_status,
        selected_region=veh_region,
    )
