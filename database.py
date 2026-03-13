# database.py
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgresql://") and "+psycopg2" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = None
SessionLocal = None

if DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        future=True,
    )
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )


def db_available() -> bool:
    return engine is not None


def test_connection():
    if engine is None:
        raise RuntimeError("DATABASE_URL não está definida.")

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        return result.fetchone()


def init_db():
    if engine is None:
        return

    schema_sql = """
    CREATE TABLE IF NOT EXISTS memories (
        id SERIAL PRIMARY KEY,
        text TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'fact',
        tags JSONB NOT NULL DEFAULT '[]'::jsonb,
        importance INTEGER NOT NULL DEFAULT 3,
        valence TEXT NOT NULL DEFAULT 'mixed',
        intensity INTEGER NOT NULL DEFAULT 50,
        pinned BOOLEAN NOT NULL DEFAULT FALSE,
        meta JSONB NOT NULL DEFAULT '{}'::jsonb,
        ts_ms BIGINT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS episodes (
        id SERIAL PRIMARY KEY,
        episode_type TEXT NOT NULL,
        summary TEXT NOT NULL,
        details JSONB NOT NULL DEFAULT '{}'::jsonb,
        tags JSONB NOT NULL DEFAULT '[]'::jsonb,
        importance INTEGER NOT NULL DEFAULT 5,
        ts_ms BIGINT NOT NULL
    );
    """

    with engine.begin() as conn:
        conn.execute(text(schema_sql))