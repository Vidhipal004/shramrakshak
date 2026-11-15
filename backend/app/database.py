"""SQLAlchemy engine and session factory."""

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.normalized_database_url.startswith("sqlite") else {}
engine = create_engine(settings.normalized_database_url, pool_pre_ping=True, connect_args=connect_args)
if settings.normalized_database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> None:
    """Raise the underlying SQLAlchemy error if the configured database is unavailable."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
