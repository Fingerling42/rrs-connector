from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from rrs_connector.db_models import DbBase


def make_sqlite_url(db_path: Path) -> str:
    return f"sqlite:///{db_path}"

def create_db_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(make_sqlite_url(db_path))

def initialize_database(engine: Engine) -> None:
    DbBase.metadata.create_all(engine)

def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)