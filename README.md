# TransitOps

## Setup
```
pip install -r requirements.txt
python run.py
```
Visit http://127.0.0.1:5000 — sign up for an account (any role), then log in.

## Structure
- app/models.py      — shared DB models (single source of truth)
- app/auth.py         — login/signup/logout (Person A)
- app/vehicles.py, drivers.py     — Vehicle & Driver management (Person B)
- app/trips.py, maintenance.py    — Trip lifecycle & Maintenance (Person C)
- app/fuel_expense.py, dashboard.py, reports.py — Fuel/Expense, KPI dashboard, Reports (Person D)
- app/templates/base.html — shared layout/nav (all pages extend this)
