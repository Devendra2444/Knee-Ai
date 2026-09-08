from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_session():
    """Yield a SQLAlchemy session, closing it when done."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def db_status() -> dict:
    """Quick connectivity check for the health endpoint."""
    try:
        with engine.connect() as conn:
            conn.execute(__import__('sqlalchemy').text('SELECT 1'))
        return {'status': 'connected', 'database': 'kneeai', 'engine': 'postgresql'}
    except Exception:
        return {'status': 'unavailable', 'database': 'kneeai', 'engine': 'postgresql'}
