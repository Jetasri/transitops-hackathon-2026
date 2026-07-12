"""
Reports Blueprint
==================
Per-vehicle report: fuel efficiency, operational cost, and a rough ROI
estimate. Also supports CSV export of the same table.

ASSUMPTION (placeholder — swap in a real revenue source later):
There is no revenue/fare field anywhere in the schema, so
`estimated_revenue` is approximated as:

    estimated_revenue = sum(planned_distance_km for completed trips) * 10

i.e. a flat $10-per-planned-km figure for completed trips only. This is
a stand-in the team agreed to use for the hackathon demo; replace with
a real revenue/billing figure if one becomes available.
"""

import csv
import io

from flask import Blueprint, render_template, Response
from flask_login import login_required

from app.models import Vehicle, Trip, FuelLog
from app.fuel_expense import get_operational_cost

reports_bp = Blueprint("reports_bp", __name__, url_prefix="/reports")

REVENUE_PER_KM = 10  # placeholder assumption — see module docstring


def _build_report_rows():
    """Compute the per-vehicle report data used by both index() and export_csv()."""
    rows = []

    for vehicle in Vehicle.query.order_by(Vehicle.reg_number).all():
        completed_trips = [t for t in vehicle.trips if t.status == "Completed"]
        total_planned_km = sum(t.planned_distance_km for t in completed_trips)

        total_fuel_liters = sum(
            fl.liters for fl in FuelLog.query.filter_by(vehicle_id=vehicle.id).all()
        )

        if total_fuel_liters > 0:
            fuel_efficiency = round(total_planned_km / total_fuel_liters, 2)
        else:
            fuel_efficiency = None  # rendered as "N/A"

        operational_cost = get_operational_cost(vehicle.id)

        estimated_revenue = total_planned_km * REVENUE_PER_KM
        if vehicle.acquisition_cost:
            vehicle_roi = round(
                (estimated_revenue - operational_cost) / vehicle.acquisition_cost, 4
            )
        else:
            vehicle_roi = None  # rendered as "N/A"

        rows.append(
            {
                "vehicle": vehicle,
                "fuel_efficiency": fuel_efficiency,
                "operational_cost": round(operational_cost, 2),
                "estimated_revenue": round(estimated_revenue, 2),
                "vehicle_roi": vehicle_roi,
            }
        )

    return rows


@reports_bp.route("/", methods=["GET"])
@login_required
def index():
    rows = _build_report_rows()
    return render_template("reports/index.html", rows=rows, revenue_per_km=REVENUE_PER_KM)


@reports_bp.route("/export.csv", methods=["GET"])
@login_required
def export_csv():
    rows = _build_report_rows()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Vehicle Reg Number",
            "Vehicle Name",
            "Fuel Efficiency (km/L)",
            "Operational Cost",
            "Estimated Revenue",
            "Vehicle ROI",
        ]
    )

    for row in rows:
        writer.writerow(
            [
                row["vehicle"].reg_number,
                row["vehicle"].name,
                row["fuel_efficiency"] if row["fuel_efficiency"] is not None else "N/A",
                row["operational_cost"],
                row["estimated_revenue"],
                row["vehicle_roi"] if row["vehicle_roi"] is not None else "N/A",
            ]
        )

    csv_data = buffer.getvalue()
    buffer.close()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=vehicle_report.csv"},
    )
