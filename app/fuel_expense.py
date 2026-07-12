"""
Fuel / Expense Blueprint
========================
Routes for logging fuel purchases and miscellaneous vehicle expenses
(tolls, fines, parking, etc.).

Exposes `get_operational_cost(vehicle_id)` which is imported by
app/reports.py to compute per-vehicle operational cost.
"""

from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from app import db
from app.models import Vehicle, FuelLog, MaintenanceLog, Expense

fuel_bp = Blueprint("fuel_bp", __name__, url_prefix="/fuel")


# ---------------------------------------------------------------------------
# Shared helper — imported by app/reports.py
# ---------------------------------------------------------------------------
def get_operational_cost(vehicle_id: int) -> float:
    """
    Total operational cost for a vehicle = all-time FuelLog.cost
    + all-time MaintenanceLog.cost (regardless of status/date).
    """
    fuel_total = (
        db.session.query(db.func.coalesce(db.func.sum(FuelLog.cost), 0.0))
        .filter(FuelLog.vehicle_id == vehicle_id)
        .scalar()
    )
    maintenance_total = (
        db.session.query(db.func.coalesce(db.func.sum(MaintenanceLog.cost), 0.0))
        .filter(MaintenanceLog.vehicle_id == vehicle_id)
        .scalar()
    )
    return float(fuel_total) + float(maintenance_total)


# ---------------------------------------------------------------------------
# Fuel logs
# ---------------------------------------------------------------------------
@fuel_bp.route("/", methods=["GET"])
@login_required
def list_fuel_logs():
    vehicle_id = request.args.get("vehicle_id", type=int)

    query = FuelLog.query
    if vehicle_id:
        query = query.filter(FuelLog.vehicle_id == vehicle_id)

    fuel_logs = query.order_by(FuelLog.date.desc()).all()
    vehicles = Vehicle.query.order_by(Vehicle.reg_number).all()

    return render_template(
        "fuel/list_fuel_logs.html",
        fuel_logs=fuel_logs,
        vehicles=vehicles,
        selected_vehicle_id=vehicle_id,
    )


@fuel_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_fuel_log():
    vehicles = Vehicle.query.order_by(Vehicle.reg_number).all()

    if request.method == "POST":
        vehicle_id = request.form.get("vehicle_id", type=int)
        liters = request.form.get("liters", type=float)
        cost = request.form.get("cost", type=float)
        log_date = request.form.get("date") or date.today().isoformat()

        if not vehicle_id or liters is None or cost is None:
            flash("Vehicle, liters, and cost are all required.", "danger")
            return render_template("fuel/new_fuel_log.html", vehicles=vehicles)

        fuel_log = FuelLog(
            vehicle_id=vehicle_id,
            liters=liters,
            cost=cost,
            date=date.fromisoformat(log_date),
        )
        db.session.add(fuel_log)
        db.session.commit()

        flash("Fuel log recorded.", "success")
        return redirect(url_for("fuel_bp.list_fuel_logs"))

    return render_template("fuel/new_fuel_log.html", vehicles=vehicles)


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------
@fuel_bp.route("/expenses", methods=["GET"])
@login_required
def list_expenses():
    vehicle_id = request.args.get("vehicle_id", type=int)

    query = Expense.query
    if vehicle_id:
        query = query.filter(Expense.vehicle_id == vehicle_id)

    expenses = query.order_by(Expense.date.desc()).all()
    vehicles = Vehicle.query.order_by(Vehicle.reg_number).all()

    return render_template(
        "fuel/list_expenses.html",
        expenses=expenses,
        vehicles=vehicles,
        selected_vehicle_id=vehicle_id,
    )


@fuel_bp.route("/expenses/new", methods=["GET", "POST"])
@login_required
def new_expense():
    vehicles = Vehicle.query.order_by(Vehicle.reg_number).all()

    if request.method == "POST":
        vehicle_id = request.form.get("vehicle_id", type=int)
        expense_type = request.form.get("type")
        amount = request.form.get("amount", type=float)
        expense_date = request.form.get("date") or date.today().isoformat()

        if not vehicle_id or not expense_type or amount is None:
            flash("Vehicle, type, and amount are all required.", "danger")
            return render_template("fuel/new_expense.html", vehicles=vehicles)

        expense = Expense(
            vehicle_id=vehicle_id,
            type=expense_type,
            amount=amount,
            date=date.fromisoformat(expense_date),
        )
        db.session.add(expense)
        db.session.commit()

        flash("Expense recorded.", "success")
        return redirect(url_for("fuel_bp.list_expenses"))

    return render_template("fuel/new_expense.html", vehicles=vehicles)
