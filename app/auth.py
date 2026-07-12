"""
TransitOps — Auth Blueprint
============================
Handles login, signup, logout, and role-based access control.

Other blueprints should import the decorator like this:
    from app.auth import role_required

    @some_bp.route("/some-protected-page")
    @role_required("fleet_manager", "safety_officer")
    def some_view():
        ...
"""

from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_user, logout_user, login_required, current_user

from app import db
from app.models import User

auth_bp = Blueprint("auth", __name__)

VALID_ROLES = ("fleet_manager", "driver", "safety_officer", "financial_analyst")


# ---------------------------------------------------------------------------
# Access control decorator
# ---------------------------------------------------------------------------
def role_required(*roles):
    """Restrict a view to users whose .role is in `roles`.

    Usage:
        @role_required("fleet_manager", "safety_officer")
        def some_view(): ...
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html")

        login_user(user)
        return redirect(url_for("dashboard_bp.index"))

    return render_template("auth/login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "driver")

        if role not in VALID_ROLES:
            role = "driver"

        if not name or not email or not password:
            flash("Please fill in all fields.", "danger")
            return render_template("auth/signup.html", roles=VALID_ROLES)

        existing = User.query.filter_by(email=email).first()
        if existing is not None:
            flash("An account with that email already exists.", "danger")
            return render_template("auth/signup.html", roles=VALID_ROLES)

        user = User(name=name, email=email, role=role)
        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Could not create account. Please try again.", "danger")
            return render_template("auth/signup.html", roles=VALID_ROLES)

        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/signup.html", roles=VALID_ROLES)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
