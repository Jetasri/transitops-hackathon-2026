"""
TransitOps — Shared Database Models
====================================
This file is the SINGLE SOURCE OF TRUTH for the whole team.
Every teammate's blueprint file should `from app.models import ...`
and NOT redefine these classes or rename any fields.

Import in your blueprint like this:
    from app import db
    from app.models import Vehicle, Driver, Trip, MaintenanceLog, FuelLog, Expense, User
"""

from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

from app import db


# ---------------------------------------------------------------------------
# USER / AUTH  (owned by Person A)
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # RBAC role — one of: fleet_manager, driver, safety_officer, financial_analyst
    role = db.Column(db.String(30), nullable=False, default="driver")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


# ---------------------------------------------------------------------------
# VEHICLE  (owned by Person B)
# ---------------------------------------------------------------------------
class Vehicle(db.Model):
    __tablename__ = "vehicles"

    VALID_STATUSES = ("Available", "On Trip", "In Shop", "Retired")

    id = db.Column(db.Integer, primary_key=True)
    reg_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)          # Vehicle Name/Model
    type = db.Column(db.String(50), nullable=False)            # e.g. Truck, Van, Bike
    max_load_kg = db.Column(db.Float, nullable=False)          # Maximum Load Capacity
    odometer = db.Column(db.Float, default=0)
    acquisition_cost = db.Column(db.Float, default=0)
    region = db.Column(db.String(80), nullable=True)           # used for dashboard filters
    status = db.Column(db.String(20), nullable=False, default="Available")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    trips = db.relationship("Trip", backref="vehicle", lazy=True)
    maintenance_logs = db.relationship("MaintenanceLog", backref="vehicle", lazy=True)
    fuel_logs = db.relationship("FuelLog", backref="vehicle", lazy=True)
    expenses = db.relationship("Expense", backref="vehicle", lazy=True)

    def is_dispatchable(self) -> bool:
        """Retired / In Shop / On Trip vehicles must never appear in dispatch pool."""
        return self.status == "Available"

    def __repr__(self):
        return f"<Vehicle {self.reg_number} ({self.status})>"


# ---------------------------------------------------------------------------
# DRIVER  (owned by Person B)
# ---------------------------------------------------------------------------
class Driver(db.Model):
    __tablename__ = "drivers"

    VALID_STATUSES = ("Available", "On Trip", "Off Duty", "Suspended")

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    license_number = db.Column(db.String(50), unique=True, nullable=False)
    license_category = db.Column(db.String(30), nullable=True)
    license_expiry = db.Column(db.Date, nullable=False)
    contact_number = db.Column(db.String(20), nullable=True)
    safety_score = db.Column(db.Float, default=100.0)
    status = db.Column(db.String(20), nullable=False, default="Available")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    trips = db.relationship("Trip", backref="driver", lazy=True)

    def is_license_valid(self) -> bool:
        return self.license_expiry >= date.today()

    def is_assignable(self) -> bool:
        """Expired-license or Suspended drivers cannot be assigned to trips."""
        return self.status == "Available" and self.is_license_valid()

    def __repr__(self):
        return f"<Driver {self.name} ({self.status})>"


# ---------------------------------------------------------------------------
# TRIP  (owned by Person C)
# ---------------------------------------------------------------------------
class Trip(db.Model):
    __tablename__ = "trips"

    VALID_STATUSES = ("Draft", "Dispatched", "Completed", "Cancelled")

    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(120), nullable=False)
    destination = db.Column(db.String(120), nullable=False)

    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id"), nullable=False)

    cargo_weight_kg = db.Column(db.Float, nullable=False)
    planned_distance_km = db.Column(db.Float, nullable=False)

    status = db.Column(db.String(20), nullable=False, default="Draft")

    # filled in when trip is completed
    final_odometer = db.Column(db.Float, nullable=True)
    fuel_consumed_l = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    dispatched_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Trip {self.id} {self.source}->{self.destination} ({self.status})>"


# ---------------------------------------------------------------------------
# MAINTENANCE LOG  (owned by Person C)
# ---------------------------------------------------------------------------
class MaintenanceLog(db.Model):
    __tablename__ = "maintenance_logs"

    VALID_STATUSES = ("Active", "Closed")

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    description = db.Column(db.String(255), nullable=False)   # e.g. "Oil Change"
    cost = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), nullable=False, default="Active")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<MaintenanceLog {self.id} vehicle={self.vehicle_id} ({self.status})>"


# ---------------------------------------------------------------------------
# FUEL LOG  (owned by Person D)
# ---------------------------------------------------------------------------
class FuelLog(db.Model):
    __tablename__ = "fuel_logs"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    liters = db.Column(db.Float, nullable=False)
    cost = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)

    def __repr__(self):
        return f"<FuelLog {self.id} vehicle={self.vehicle_id} {self.liters}L>"


# ---------------------------------------------------------------------------
# EXPENSE  (owned by Person D)  — tolls, misc costs (maintenance cost lives on MaintenanceLog)
# ---------------------------------------------------------------------------
class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    type = db.Column(db.String(50), nullable=False)   # e.g. "Toll", "Fine", "Parking"
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)

    def __repr__(self):
        return f"<Expense {self.id} vehicle={self.vehicle_id} {self.type} {self.amount}>"
