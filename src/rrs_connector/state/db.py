"""Database engine, schema initialization, and session factory helpers."""

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from rrs_connector.state.models import DbBase


def make_sqlite_url(db_path: Path) -> str:
    """Build a SQLAlchemy SQLite URL from a filesystem path."""

    return f"sqlite:///{db_path}"


def create_db_engine(db_path: Path) -> Engine:
    """Create a SQLAlchemy engine for the local SQLite state database."""

    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(make_sqlite_url(db_path))


def initialize_database(engine: Engine) -> None:
    """Create all known state database tables if they do not exist."""

    DbBase.metadata.create_all(engine)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create short-lived SQLAlchemy sessions bound to the given engine."""

    return sessionmaker(bind=engine, expire_on_commit=False)
