import os
from collections.abc import Callable, Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def get_database_url() -> str:
    """Construct the database connection URL from environment variables.

    Reads DB_HOST, DB_PORT, DB_NAME, DB_USER, and DB_PASSWORD with
    development-friendly defaults when variables are absent.

    Returns:
        str: PostgreSQL connection URL as a string.
    """
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "security_master")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "")

    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


def create_db_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine with connection pooling configured.

    Args:
        database_url (str | None): PostgreSQL connection URL. When None, calls
            get_database_url() to read from environment variables.

    Returns:
        Engine: SQLAlchemy Engine with pool_pre_ping enabled and pool_recycle=300.
    """
    if database_url is None:
        database_url = get_database_url()

    return create_engine(
        database_url,
        echo=os.getenv("DB_ECHO", "false").lower() == "true",
        pool_pre_ping=True,
        pool_recycle=300,
    )


def create_tables(engine: Engine) -> None:
    """Create all ORM-mapped tables in the target database if they do not exist.

    Args:
        engine (Engine): SQLAlchemy Engine connected to the target database.
    """
    Base.metadata.create_all(bind=engine)


def get_session_factory(engine: Engine) -> Callable[[], Session]:
    """Build a callable session factory bound to the given engine.

    Args:
        engine (Engine): SQLAlchemy Engine to bind new sessions to.

    Returns:
        Callable[[], Session]: Callable that returns a fresh Session on each invocation.
    """
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session(
    session_factory: Callable[[], Session],
) -> Generator[Session, None, None]:
    """Yield a database session that commits on success and rolls back on error.

    Commits automatically on clean exit. Rolls back and re-raises on any
    exception. Always closes the session in the finally block.

    Args:
        session_factory (Callable[[], Session]): Callable that produces a new Session instance.

    Yields:
        Session: An active, open database Session.

    Raises:
        Exception: Re-raises any exception after rolling back the session.
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
