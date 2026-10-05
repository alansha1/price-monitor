"""
Database setup and session management.
Uses SQLite for local development; swap DATABASE_URL in .env for PostgreSQL in prod.
"""

import os
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase


# Make sure the SQLite folder exists before we try to open the database file.
def ensure_database_directory(database_url: str) -> None:
    """Create the parent directory for SQLite database files if it does not exist."""
    if not database_url.startswith("sqlite"):
        return

    parsed = urlparse(database_url)
    db_path = parsed.path
    if not db_path or db_path in {":memory:"}:
        return

    if database_url.startswith("sqlite:////"):
        path = db_path
    elif database_url.startswith("sqlite:///"):
        path = db_path[1:] if db_path.startswith("/") else db_path
    else:
        return

    path = os.path.abspath(path)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


# Database connection settings used by the app.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/price_monitor.db")
ensure_database_directory(DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

# SQLAlchemy session factory for each request.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# Give each API request a database session, then close it after use.
def get_db():
    """Dependency: yields a DB session, ensures it closes after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
