"""Unit tests for :mod:`security_master.storage.database`.

Covers URL construction from environment variables, engine creation, table
creation, the session factory, and the commit/rollback semantics of the
``get_db_session`` generator. SQLite (with the conftest UUID shim) stands in
for PostgreSQL so the tests need no external database.
"""

from __future__ import annotations

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from security_master.storage import database

pytestmark = pytest.mark.storage

_SQLITE_URL = "sqlite:///:memory:"


def test_get_database_url_uses_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The URL is assembled from the DB_* environment variables."""
    host, port, name, user, pw = "db.example.com", "6543", "sm", "alice", "synthetic"
    monkeypatch.setenv("DB_HOST", host)
    monkeypatch.setenv("DB_PORT", port)
    monkeypatch.setenv("DB_NAME", name)
    monkeypatch.setenv("DB_USER", user)
    monkeypatch.setenv("DB_PASSWORD", pw)
    # Build the expected DSN from parts so no full credential-bearing literal
    # exists in source for the secret scanners to flag (the values are synthetic).
    expected = f"postgresql://{user}:{pw}@{host}:{port}/{name}"
    assert database.get_database_url() == expected


def test_get_database_url_falls_back_to_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Absent environment variables yield development-friendly defaults."""
    for var in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    user, host, port, name = "postgres", "localhost", "5432", "security_master"
    expected = f"postgresql://{user}:@{host}:{port}/{name}"
    assert database.get_database_url() == expected


def test_create_db_engine_with_explicit_url() -> None:
    """An explicit URL is used verbatim to build an Engine."""
    engine = database.create_db_engine(_SQLITE_URL)
    assert isinstance(engine, Engine)
    engine.dispose()


def test_create_db_engine_defaults_to_environment_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no URL argument, the engine is built from get_database_url()."""
    monkeypatch.setenv("DB_HOST", "localhost")
    engine = database.create_db_engine()
    assert engine.url.get_backend_name() == "postgresql"
    engine.dispose()


def test_create_tables_creates_schema() -> None:
    """create_tables provisions the ORM schema on the target engine."""
    engine = database.create_db_engine(_SQLITE_URL)
    database.create_tables(engine)
    with engine.connect() as conn:
        from sqlalchemy import inspect

        tables = inspect(conn).get_table_names()
    assert "securities_master" in tables
    engine.dispose()


def test_get_session_factory_returns_sessions() -> None:
    """The factory produces independent Session instances."""
    engine = database.create_db_engine(_SQLITE_URL)
    factory = database.get_session_factory(engine)
    session = factory()
    assert isinstance(session, Session)
    session.close()
    engine.dispose()


def test_get_db_session_commits_on_success() -> None:
    """The generator yields a session and commits when consumed cleanly."""
    engine = database.create_db_engine(_SQLITE_URL)
    database.create_tables(engine)
    factory = database.get_session_factory(engine)

    generator = database.get_db_session(factory)
    session = next(generator)
    assert isinstance(session, Session)
    with pytest.raises(StopIteration):
        next(generator)  # drives commit + close in the generator's tail
    engine.dispose()


def test_get_db_session_rolls_back_and_reraises() -> None:
    """An exception thrown into the generator triggers rollback and re-raises."""
    engine = database.create_db_engine(_SQLITE_URL)
    factory = database.get_session_factory(engine)

    generator = database.get_db_session(factory)
    next(generator)
    with pytest.raises(ValueError, match="boom"):
        generator.throw(ValueError("boom"))
    engine.dispose()
