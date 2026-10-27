"""Exercise the new revision against an isolated SQLite schema at 0003."""
import os
import sqlite3
import tempfile

from flask_migrate import upgrade
from sqlalchemy import inspect
from app import create_app


def test_customer_portal_revision_upgrades_existing_schema():
    db_path = tempfile.mktemp(prefix="tripleforce-migration-", suffix=".db")

    class MigrationConfig:
        TESTING = True
        SECRET_KEY = "migration-test"
        WTF_CSRF_ENABLED = False
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + db_path
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
        UPLOAD_FOLDER = tempfile.mkdtemp(prefix="tripleforce-migration-files-")
        AUTO_CREATE_SCHEMA = False

    connection = sqlite3.connect(db_path)
    connection.executescript(
        "CREATE TABLE customers (id INTEGER PRIMARY KEY);"
        "CREATE TABLE users (id INTEGER PRIMARY KEY);"
        "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);"
        "INSERT INTO alembic_version VALUES ('0003_pricing_rate_card');"
    )
    connection.close()
    app = create_app(MigrationConfig)
    try:
        with app.app_context():
            upgrade(directory=os.path.abspath("migrations"))
            inspector = inspect(app.extensions["sqlalchemy"].engine)
            assert "customer_id" in {c["name"] for c in inspector.get_columns("users")}
            assert {"customer_account_requests", "customer_invitations"}.issubset(set(inspector.get_table_names()))
            assert inspector.get_foreign_keys("users")[0]["referred_table"] == "customers"
    finally:
        os.unlink(db_path)


def test_runtime_schema_adds_customer_link_for_railway_startup():
    db_path = tempfile.mktemp(prefix="tripleforce-runtime-migration-", suffix=".db")

    class RuntimeConfig:
        TESTING = True
        SECRET_KEY = "runtime-migration-test"
        WTF_CSRF_ENABLED = False
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + db_path
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
        UPLOAD_FOLDER = tempfile.mkdtemp(prefix="tripleforce-runtime-files-")
        AUTO_CREATE_SCHEMA = True

    connection = sqlite3.connect(db_path)
    connection.executescript(
        "CREATE TABLE customers (id INTEGER PRIMARY KEY);"
        "CREATE TABLE users (id INTEGER PRIMARY KEY);"
    )
    connection.close()
    app = create_app(RuntimeConfig)
    try:
        with app.app_context():
            inspector = inspect(app.extensions["sqlalchemy"].engine)
            user_columns = {c["name"] for c in inspector.get_columns("users")}
            user_indexes = {i["name"] for i in inspector.get_indexes("users")}
            assert "customer_id" in user_columns
            assert "ix_users_customer_id" in user_indexes
            assert {"customer_account_requests", "customer_invitations"}.issubset(
                set(inspector.get_table_names())
            )
    finally:
        os.unlink(db_path)
