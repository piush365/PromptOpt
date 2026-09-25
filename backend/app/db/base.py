"""Engine, session factory and declarative base."""
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_URL, SQL_ECHO


class Base(DeclarativeBase):
    pass


def make_engine(url: str = DATABASE_URL) -> Engine:
    kwargs = {"echo": SQL_ECHO, "future": True}
    if url.startswith("sqlite"):
        # FastAPI may use the session from a different thread than the one that created it
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True
    return create_engine(url, **kwargs)


@event.listens_for(Engine, "connect")
def _sqlite_enable_foreign_keys(dbapi_connection, connection_record):
    # SQLite ignores foreign keys (and ON DELETE CASCADE) unless this is switched on per connection.
    # The retention purge relies on the cascade, so it must be on.
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: `def route(db: Session = Depends(get_db))`."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
