"""Database engine, session management, and CI migration entrypoint for Cloud SQL Postgres."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql+psycopg://postgres:local@localhost:5432/app")


engine = create_engine(get_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def run_migrations(repo_root: Path | None = None) -> int:
    """Run Alembic migrations (`alembic upgrade head`) when alembic.ini is present, else create metadata."""
    root = repo_root or Path(__file__).resolve().parents[2]
    alembic_ini = root / "alembic.ini"
    if alembic_ini.is_file():
        res = subprocess.run(["alembic", "-c", str(alembic_ini), "upgrade", "head"], check=False)
        return res.returncode
    Base.metadata.create_all(bind=engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_migrations())
