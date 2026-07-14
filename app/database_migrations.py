from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.config import BASE_DIR
from app.database import engine
from app.models import User


def run_migrations() -> None:
    """Upgrade a new or existing database without losing pre-Alembic data."""
    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BASE_DIR / "migrations"))
    tables = set(inspect(engine).get_table_names())
    if "alembic_version" not in tables and "sessions" in tables:
        if "users" not in tables:
            User.__table__.create(engine, checkfirst=True)
        session_columns = {column["name"] for column in inspect(engine).get_columns("sessions")}
        command.stamp(config, "head" if "location" in session_columns else "0001_baseline")
    command.upgrade(config, "head")
