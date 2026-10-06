"""``pp-master`` commands for account balances.

- ``nightly-totals``: total each IBKR account (positions plus cash) for the
  latest report date and write ``account_balances`` rows.
- ``balance set`` / ``balance list``: record and show manual marks.

Output and error text never contains a balance except in ``balance list``,
whose purpose is to show values (always as two-place decimal strings).
Database errors are reported with fixed text, because a driver message can
embed the bound parameters (values and keys) of the failed statement.
"""

from __future__ import annotations

import getpass
import json
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import click
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from security_master.balances.ibkr_totals import compute_nightly_totals
from security_master.balances.registry import RegistryError, load_registry
from security_master.balances.rules import (
    SOURCE_MANUAL_MARK,
    BalanceRuleError,
    parse_money,
)
from security_master.balances.service import (
    MANUAL_SOURCES,
    list_balances,
    set_manual_balance,
)
from security_master.storage.database import (
    create_db_engine,
    create_tables,
    get_session_factory,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from datetime import date, datetime

    from sqlalchemy.orm import Session

    from security_master.balances.registry import AccountRegistry

_REGISTRY_HELP = (
    "Account registry seed (YAML) outside the repo. Defaults to the "
    "PP_ACCOUNT_REGISTRY_PATH setting."
)


def _common_options(func: Callable[..., None]) -> Callable[..., None]:
    """Attach the database, registry, and schema options shared by all commands.

    Args:
        func: The click command function to decorate.

    Returns:
        The decorated function.
    """
    func = click.option(
        "--create-schema/--no-create-schema",
        default=False,
        show_default=True,
        help="Create tables first (useful for a fresh database).",
    )(func)
    func = click.option(
        "--registry-path",
        type=click.Path(dir_okay=False, path_type=Path),
        default=None,
        help=_REGISTRY_HELP,
    )(func)
    return click.option(
        "--database-url",
        default=None,
        help="Override database URL. Defaults to DB_* environment variables.",
    )(func)


def _load_registry_or_fail(registry_path: Path | None) -> AccountRegistry:
    """Load the registry, converting failures to a clean CLI error.

    Args:
        registry_path: Optional explicit seed path.

    Returns:
        The validated account registry.

    Raises:
        click.ClickException: When the registry cannot be loaded.
    """
    try:
        return load_registry(registry_path)
    except RegistryError as exc:
        raise click.ClickException(str(exc)) from exc


_CONFLICT_MESSAGE = (
    "the database refused the write: a balance for this account and date "
    "already exists (possibly written concurrently); nothing was saved"
)
_DB_ERROR_MESSAGE = (
    "database error; nothing was saved. Check --database-url or the DB_* "
    "settings, and that the schema is migrated"
)


@contextmanager
def _db_session(database_url: str | None, *, create_schema: bool) -> Generator[Session]:
    """Open a session for one command, and always dispose of the engine.

    The caller commits. Any exception rolls the session back. Database errors
    become a ``ClickException`` with fixed text so no bound parameter (a
    balance or an account key) reaches the terminal.

    Args:
        database_url: Optional database URL override.
        create_schema: Create the tables first.

    Yields:
        An open session.

    Raises:
        click.ClickException: On any SQLAlchemy error.
    """
    engine = create_db_engine(database_url)
    try:
        if create_schema:
            create_tables(engine)
        session = get_session_factory(engine)()
        completed = False
        try:
            yield session
            completed = True
        finally:
            # An exception from the command body (or an interrupt) leaves
            # ``completed`` False; undo any uncommitted work before closing.
            if not completed:
                session.rollback()
            session.close()
    except IntegrityError:
        raise click.ClickException(_CONFLICT_MESSAGE) from None
    except SQLAlchemyError:
        raise click.ClickException(_DB_ERROR_MESSAGE) from None
    finally:
        engine.dispose()


@click.command("nightly-totals")
@_common_options
def nightly_totals(
    database_url: str | None, registry_path: Path | None, *, create_schema: bool
) -> None:
    """Total each IBKR account (positions plus cash) for the latest report date.

    Writes one account_balances row per account with source ibkr_flex. USD only:
    non-USD rows are rejected with a log line, never converted. Exits non-zero
    when any account was withheld so a scheduler notices.
    """
    # Rejections are logged; make sure they reach stderr when run standalone.
    # basicConfig is a no-op when the host already configured logging.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    registry = _load_registry_or_fail(registry_path)
    with _db_session(database_url, create_schema=create_schema) as session:
        result = compute_nightly_totals(session, registry)
        session.commit()

    if result.report_date is None:
        msg = "no IBKR positions have been imported; nothing to total"
        raise click.ClickException(msg)
    click.echo(
        f"Report date {result.report_date.isoformat()}: "
        f"wrote {result.inserted}, updated {result.updated}, "
        f"withheld {result.accounts_withheld} account(s)."
    )
    if result.accounts_withheld:
        raise SystemExit(1)


@click.group("balance")
def balance() -> None:
    """Record and list account balances."""


def _default_entered_by() -> str:
    """Return the OS user name to attribute a mark to when none is given.

    Returns:
        The current OS user name, or an empty string when it cannot be found.
    """
    try:
        return getpass.getuser()
    except (KeyError, OSError):
        return ""


@balance.command("set")
@click.option("--account", "account_key", required=True, help="Account key (pp:...).")
@click.option("--value", "value_text", required=True, help="USD value, e.g. 1234.56.")
@click.option(
    "--as-of",
    "as_of",
    required=True,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Statement date (YYYY-MM-DD).",
)
@click.option(
    "--source",
    type=click.Choice(MANUAL_SOURCES),
    default=SOURCE_MANUAL_MARK,
    show_default=True,
)
@click.option("--note", default=None, help="Free-text note (at most 500 characters).")
@click.option(
    "--entered-by",
    default=None,
    help="Who is entering this mark. Defaults to the OS user name.",
)
@click.option(
    "--replace",
    is_flag=True,
    default=False,
    help="Overwrite an existing mark for the same account and date.",
)
@_common_options
def balance_set(
    account_key: str,
    value_text: str,
    as_of: datetime,
    source: str,
    note: str | None,
    entered_by: str | None,
    database_url: str | None,
    registry_path: Path | None,
    *,
    create_schema: bool,
    replace: bool,
) -> None:
    """Record a manual balance mark for a mapped account."""
    try:
        value = parse_money(value_text)
    except BalanceRuleError as exc:
        raise click.BadParameter(str(exc), param_hint="--value") from exc
    registry = _load_registry_or_fail(registry_path)
    with _db_session(database_url, create_schema=create_schema) as session:
        try:
            row = set_manual_balance(
                session,
                registry,
                account_key=account_key,
                value=value,
                as_of=as_of.date(),
                source=source,
                note=note,
                entered_by=(
                    entered_by if entered_by is not None else _default_entered_by()
                ),
                replace=replace,
            )
        except BalanceRuleError as exc:
            raise click.ClickException(str(exc)) from exc
        session.commit()
        message = (
            f"Recorded {row.source} for {row.account_key} as of "
            f"{row.as_of.isoformat()} (entered by {row.entered_by})."
        )
    click.echo(message)


@balance.command("list")
@click.option(
    "--as-of",
    "as_of",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Show only the balance for exactly this date (default: latest per account).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@_common_options
def balance_list(
    as_of: datetime | None,
    output_format: str,
    database_url: str | None,
    registry_path: Path | None,
    *,
    create_schema: bool,
) -> None:
    """List every mapped account with its balance (values as decimal strings)."""
    registry = _load_registry_or_fail(registry_path)
    as_of_date: date | None = as_of.date() if as_of else None
    with _db_session(database_url, create_schema=create_schema) as session:
        rows = list_balances(session, registry, as_of=as_of_date)

    if output_format == "json":
        click.echo(json.dumps([r.as_dict() for r in rows], indent=2))
        return
    click.echo(
        f"{'ACCOUNT':<22}{'NAME':<34}{'CATEGORY':<18}{'VALUE':>20} "
        f"{'CCY':<4}{'AS OF':<11}{'SOURCE':<12}ENTERED BY"
    )
    for r in rows:
        click.echo(
            f"{r.account_key:<22}{r.display_name[:32]:<34}{r.category:<18}"
            f"{r.value or '-':>20} {r.currency or '-':<4}"
            f"{r.as_of.isoformat() if r.as_of else '-':<11}"
            f"{r.source or '-':<12}{r.entered_by or '-'}"
        )
