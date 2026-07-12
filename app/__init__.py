import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
        basedir, "..", "transitops.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Blueprints (each maps to one "person's" module from the team split)
    from .auth import auth_bp                # Person A
    from .vehicles import vehicles_bp        # Person B
    from .drivers import drivers_bp          # Person B
    from .trips import trips_bp              # Person C
    from .maintenance import maintenance_bp  # Person C
    from .fuel_expense import fuel_bp        # Person D
    from .dashboard import dashboard_bp      # Person D
    from .reports import reports_bp          # Person D

    app.register_blueprint(auth_bp)
    app.register_blueprint(vehicles_bp)
    app.register_blueprint(drivers_bp)
    app.register_blueprint(trips_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(fuel_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(reports_bp)

    with app.app_context():
        db.create_all()

    return app
