"""
TransitOps — Demo Data Seeder
==============================
Populates the database with realistic fake data for demo/video purposes.

USAGE:
    python seed_demo_data.py

WARNING: This will WIPE all existing data and start fresh. Don't run this
on data you care about — it's meant for demo prep only.

After running, log in with:
    email:    admin@transitops.com
    password: admin123
"""

import random
from datetime import date, datetime, timedelta

from app import create_app, db
from app.models import User, Vehicle, Driver, Trip, MaintenanceLog, FuelLog, Expense

app = create_app()

VEHICLE_TYPES = ["Truck", "Van", "Bike", "Mini Truck"]
REGIONS = ["North", "South", "East", "West", "Central"]

VEHICLE_NAMES = [
    ("VAN-01", "Tata Ace Gold", "Van", 750),
    ("VAN-02", "Mahindra Bolero Pickup", "Van", 1200),
    ("VAN-03", "Force Traveller", "Van", 1500),
    ("TRK-01", "Ashok Leyland Dost", "Truck", 3000),
    ("TRK-02", "Tata 407", "Truck", 2500),
    ("TRK-03", "Eicher Pro 2049", "Truck", 4500),
    ("BIKE-01", "Bajaj CT 100", "Bike", 60),
    ("BIKE-02", "Hero Splendor", "Bike", 60),
    ("MINI-01", "Piaggio Ape", "Mini Truck", 500),
    ("MINI-02", "Tata Ace", "Mini Truck", 750),
    ("VAN-04", "Maruti Eeco Cargo", "Van", 600),
    ("TRK-04", "BharatBenz 1217", "Truck", 5000),
]

DRIVER_NAMES = [
    "Alex Kumar", "Priya Sharma", "Rahul Verma", "Sneha Iyer", "Vikram Singh",
    "Anjali Nair", "Karthik Reddy", "Divya Menon", "Arjun Patel", "Meera Joseph",
]

CITIES = [
    "Chennai", "Bengaluru", "Coimbatore", "Madurai", "Hyderabad",
    "Mumbai", "Pune", "Delhi", "Kochi", "Vijayawada",
]


def rand_date_within(days_back):
    return date.today() - timedelta(days=random.randint(0, days_back))


def rand_datetime_within(days_back):
    return datetime.utcnow() - timedelta(
        days=random.randint(0, days_back), hours=random.randint(0, 23)
    )


def seed():
    with app.app_context():
        print("Wiping existing data...")
        db.drop_all()
        db.create_all()

        # ------------------------------------------------------------------
        # Users (one per role, so you can demo RBAC too)
        # ------------------------------------------------------------------
        print("Creating users...")
        users = [
            ("Admin Fleet Manager", "admin@transitops.com", "fleet_manager"),
            ("Driver User", "driver@transitops.com", "driver"),
            ("Safety Officer", "safety@transitops.com", "safety_officer"),
            ("Finance Analyst", "finance@transitops.com", "financial_analyst"),
        ]
        for name, email, role in users:
            u = User(name=name, email=email, role=role)
            u.set_password("admin123")
            db.session.add(u)
        db.session.commit()

        # ------------------------------------------------------------------
        # Vehicles
        # ------------------------------------------------------------------
        print("Creating vehicles...")
        vehicles = []
        for reg, name, vtype, capacity in VEHICLE_NAMES:
            v = Vehicle(
                reg_number=reg,
                name=name,
                type=vtype,
                max_load_kg=capacity,
                odometer=random.randint(5000, 80000),
                acquisition_cost=random.randint(300000, 2500000),
                region=random.choice(REGIONS),
                status="Available",
            )
            db.session.add(v)
            vehicles.append(v)
        db.session.commit()

        # Retire a couple, send a couple to maintenance later
        vehicles[-1].status = "Retired"
        db.session.commit()

        # ------------------------------------------------------------------
        # Drivers
        # ------------------------------------------------------------------
        print("Creating drivers...")
        drivers = []
        for i, name in enumerate(DRIVER_NAMES):
            # Most have valid licenses; a couple expired/suspended for demo realism
            if i == 8:
                expiry = date.today() - timedelta(days=30)  # expired
                status = "Available"
            elif i == 9:
                expiry = date.today() + timedelta(days=200)
                status = "Suspended"
            else:
                expiry = date.today() + timedelta(days=random.randint(60, 700))
                status = "Available"

            d = Driver(
                name=name,
                license_number=f"LIC-{1000 + i}",
                license_category=random.choice(["LMV", "HMV", "MC"]),
                license_expiry=expiry,
                contact_number=f"9{random.randint(100000000, 999999999)}",
                safety_score=round(random.uniform(70, 99), 1),
                status=status,
            )
            db.session.add(d)
            drivers.append(d)
        db.session.commit()

        assignable_drivers = [d for d in drivers if d.is_assignable()]
        dispatchable_vehicles = [v for v in vehicles if v.is_dispatchable()]

        # ------------------------------------------------------------------
        # Trips — mix of Draft, Dispatched, Completed, Cancelled
        # ------------------------------------------------------------------
        print("Creating trips...")
        trip_defs = []
        for i in range(18):
            source, dest = random.sample(CITIES, 2)
            vehicle = random.choice(vehicles[:-1])  # skip the retired one
            driver = random.choice([d for d in drivers if d.status != "Suspended"])
            distance = random.randint(50, 900)
            cargo = round(random.uniform(0.3, 0.9) * vehicle.max_load_kg, 1)

            trip = Trip(
                source=source,
                destination=dest,
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                cargo_weight_kg=cargo,
                planned_distance_km=distance,
                status="Draft",
                created_at=rand_datetime_within(45),
            )
            db.session.add(trip)
            trip_defs.append((trip, vehicle, driver, distance))
        db.session.commit()

        # Now assign realistic statuses to the trips we just made
        for idx, (trip, vehicle, driver, distance) in enumerate(trip_defs):
            roll = idx % 5
            if roll == 0:
                # leave as Draft
                continue
            elif roll == 1:
                # Cancelled
                trip.status = "Cancelled"
            elif roll in (2, 3, 4):
                # Completed (most common, gives good report data)
                trip.status = "Completed"
                trip.dispatched_at = trip.created_at + timedelta(hours=2)
                trip.completed_at = trip.dispatched_at + timedelta(hours=random.randint(4, 30))
                trip.final_odometer = vehicle.odometer + distance
                trip.fuel_consumed_l = round(distance / random.uniform(6, 12), 1)
                vehicle.odometer = trip.final_odometer

        # Make exactly 2 vehicles/drivers currently "On Trip" (Dispatched) for
        # a live dashboard demo
        live_pairs = [(trip_defs[0][1], trip_defs[0][2]), (trip_defs[6][1], trip_defs[6][2])]
        # reset those two trips specifically to Dispatched
        trip_defs[0][0].status = "Dispatched"
        trip_defs[0][0].dispatched_at = datetime.utcnow() - timedelta(hours=3)
        trip_defs[0][1].status = "On Trip"
        trip_defs[0][2].status = "On Trip"

        trip_defs[6][0].status = "Dispatched"
        trip_defs[6][0].dispatched_at = datetime.utcnow() - timedelta(hours=1)
        trip_defs[6][1].status = "On Trip"
        trip_defs[6][2].status = "On Trip"

        db.session.commit()

        # ------------------------------------------------------------------
        # Maintenance — a couple active (vehicle In Shop), a couple closed history
        # ------------------------------------------------------------------
        print("Creating maintenance logs...")
        maint_descriptions = [
            "Oil Change", "Brake Pad Replacement", "Tyre Rotation",
            "Engine Diagnostics", "AC Servicing", "Battery Replacement",
        ]

        # 2 vehicles currently in active maintenance
        in_shop_vehicles = [v for v in vehicles if v.status == "Available"][:2]
        for v in in_shop_vehicles:
            m = MaintenanceLog(
                vehicle_id=v.id,
                description=random.choice(maint_descriptions),
                cost=random.randint(1500, 12000),
                status="Active",
                created_at=rand_datetime_within(3),
            )
            v.status = "In Shop"
            db.session.add(m)

        # historical closed maintenance for several vehicles (for cost reports)
        for v in vehicles:
            for _ in range(random.randint(1, 3)):
                created = rand_datetime_within(120)
                m = MaintenanceLog(
                    vehicle_id=v.id,
                    description=random.choice(maint_descriptions),
                    cost=random.randint(800, 9000),
                    status="Closed",
                    created_at=created,
                    closed_at=created + timedelta(days=random.randint(1, 3)),
                )
                db.session.add(m)
        db.session.commit()

        # ------------------------------------------------------------------
        # Fuel logs
        # ------------------------------------------------------------------
        print("Creating fuel logs...")
        for v in vehicles:
            for _ in range(random.randint(3, 8)):
                liters = round(random.uniform(15, 60), 1)
                f = FuelLog(
                    vehicle_id=v.id,
                    liters=liters,
                    cost=round(liters * random.uniform(95, 108), 2),  # ~fuel price/L
                    date=rand_date_within(90),
                )
                db.session.add(f)
        db.session.commit()

        # ------------------------------------------------------------------
        # Expenses (tolls, fines, parking)
        # ------------------------------------------------------------------
        print("Creating expenses...")
        expense_types = ["Toll", "Parking", "Fine", "Permit Fee"]
        for v in vehicles:
            for _ in range(random.randint(1, 5)):
                e = Expense(
                    vehicle_id=v.id,
                    type=random.choice(expense_types),
                    amount=random.randint(50, 2000),
                    date=rand_date_within(90),
                )
                db.session.add(e)
        db.session.commit()

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print()
        print("=" * 50)
        print("Demo data seeded successfully!")
        print("=" * 50)
        print(f"  Users:        {User.query.count()}")
        print(f"  Vehicles:     {Vehicle.query.count()}")
        print(f"  Drivers:      {Driver.query.count()}")
        print(f"  Trips:        {Trip.query.count()}")
        print(f"  Maintenance:  {MaintenanceLog.query.count()}")
        print(f"  Fuel logs:    {FuelLog.query.count()}")
        print(f"  Expenses:     {Expense.query.count()}")
        print()
        print("Login with:")
        print("  Fleet Manager   -> admin@transitops.com   / admin123")
        print("  Driver          -> driver@transitops.com  / admin123")
        print("  Safety Officer  -> safety@transitops.com  / admin123")
        print("  Finance Analyst -> finance@transitops.com / admin123")
        print("=" * 50)


if __name__ == "__main__":
    seed()
