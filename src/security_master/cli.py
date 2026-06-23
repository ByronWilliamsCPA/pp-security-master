"""Command-line interface for the Security Master service.

Exposes these commands under the ``pp-master`` group:

- ``import-xml`` / ``export-xml``: move a Portfolio Performance ``client.xml``
  backup in and out of the database.
- ``import-broker``: ingest a broker export (currently IBKR Flex Query XML) into
  the transactions store.
- ``classify``: a sub-group for Tier-4 manual classification (gics-sector,
  sleeve, cash, crypto-seed) that locks a row against automated overwrite.

Database connection details are read from the environment (see
:func:`security_master.storage.database.get_database_url`).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import click

from security_master.classifier import (
    AssignmentKind,
    ClassificationLockedError,
    ManualAssignment,
    apply_manual_classification,
)
from security_master.classifier.crypto_seed import apply_crypto_seed
from security_master.classifier.taxonomy_lookup import (
    CASH_LEVEL1,
    UnknownClassificationValueError,
    resolve_brx_plus_sleeve,
    resolve_gics_sector,
)
from security_master.extractor import IBKRFlexImportService, IBKRPositionsImportService
from security_master.patch.pp_xml_export import PPXMLExportService
from security_master.patch.pp_xml_import import PPXMLImportService
from security_master.storage.database import (
    create_db_engine,
    create_tables,
    get_session_factory,
)
from security_master.storage.models import SecurityMaster
from security_master.storage.position_models import InteractiveBrokersOpenPosition
from security_master.storage.position_reconciliation import (
    DEFAULT_TOLERANCE,
    reconcile_positions,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.orm import Session

# Institutions whose broker files import-broker can ingest today.
_SUPPORTED_INSTITUTIONS = ("ibkr",)


@click.group()
def app() -> None:
    """Security Master command line interface."""


@app.command("import-xml")
@click.argument(
    "xml_file",
    type=click.Path(exists=True, dir_okay=False, readable=True),
)
@click.option(
    "--config-name",
    default="default",
    show_default=True,
    help="Name to assign to the imported PP client configuration.",
)
@click.option(
    "--create-schema/--no-create-schema",
    default=False,
    show_default=True,
    help="Create database tables before importing (for an empty database).",
)
def import_xml(xml_file: str, config_name: str, *, create_schema: bool) -> None:
    """Import a Portfolio Performance client.xml backup into the database."""
    engine = create_db_engine()
    if create_schema:
        create_tables(engine)
    session = get_session_factory(engine)()
    try:
        summary = PPXMLImportService(session).import_from_file(xml_file, config_name)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()

    click.echo(
        f"Imported {summary.securities} securities, {summary.prices} prices, "
        f"{summary.accounts} accounts, {summary.portfolios} portfolios, "
        f"{summary.bookmarks} bookmarks (PP client version "
        f"{summary.config_version}).",
    )


@app.command("export-xml")
@click.argument("output_file", type=click.Path(dir_okay=False, writable=True))
@click.option(
    "--config-name",
    default="default",
    show_default=True,
    help="Name of the active PP client configuration to export.",
)
def export_xml(output_file: str, config_name: str) -> None:
    """Export the database to a Portfolio Performance client.xml backup."""
    engine = create_db_engine()
    session = get_session_factory(engine)()
    try:
        PPXMLExportService(session).export_to_file(output_file, config_name)
    finally:
        session.close()
        engine.dispose()

    click.echo(f"Exported Portfolio Performance backup to {output_file}.")


@app.command("import-broker")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--institution",
    default="ibkr",
    show_default=True,
    help="Broker file format to import. Only 'ibkr' is supported for now.",
)
@click.option(
    "--database-url",
    default=None,
    help="Override database URL. Defaults to DB_* environment variables.",
)
@click.option(
    "--create-schema/--no-create-schema",
    default=False,
    show_default=True,
    help="Create tables before importing (useful for a fresh database).",
)
def import_broker(
    file: str,
    institution: str,
    database_url: str | None,
    create_schema: bool,
) -> None:
    """Import a broker FILE into the transactions store.

    FILE is the path to the broker export to ingest. The --institution option
    selects the parser; only 'ibkr' (IBKR Flex Query XML) is wired today.
    """
    if institution not in _SUPPORTED_INSTITUTIONS:
        supported = ", ".join(_SUPPORTED_INSTITUTIONS)
        msg = (
            f"Unsupported institution '{institution}'. "
            f"Supported institutions: {supported}."
        )
        raise click.BadParameter(msg, param_hint="--institution")

    engine = create_db_engine(database_url)
    if create_schema:
        create_tables(engine)

    session_factory = get_session_factory(engine)
    session = session_factory()
    try:
        service = IBKRFlexImportService(session)
        summary = service.import_from_file(file)
    finally:
        session.close()

    click.echo(
        f"Imported {summary.trades} trade(s), "
        f"{summary.cash_transactions} cash transaction(s), "
        f"{summary.corporate_actions} corporate action(s), "
        f"{summary.transfers} transfer(s) "
        f"(skipped {summary.skipped} existing) "
        f"from {file} as batch {summary.import_batch_id}."
    )


def _find_security(
    session: Session, isin: str | None, security_id: int | None
) -> SecurityMaster:
    """Look up one security by ISIN or primary key.

    Args:
        session: Active database session.
        isin: ISIN to match (primary selector).
        security_id: Primary key to match (alternative selector).

    Returns:
        The matching SecurityMaster.

    Raises:
        click.ClickException: If both selectors are given, neither selector is
            given, or no row matches.
    """
    if isin and security_id is not None:
        msg = "provide exactly one of --isin or --id, not both"
        raise click.ClickException(msg)
    if isin:
        sec = session.query(SecurityMaster).filter_by(isin=isin).one_or_none()
    elif security_id is not None:
        sec = session.get(SecurityMaster, security_id)
    else:
        msg = "provide --isin or --id to select a security"
        raise click.ClickException(msg)
    if sec is None:
        msg = f"no security found for isin={isin!r} id={security_id!r}"
        raise click.ClickException(msg)
    return sec


def _run_assignment(
    isin: str | None,
    security_id: int | None,
    assignment: ManualAssignment,
    classified_by: str,
    *,
    force: bool,
) -> None:
    """Apply a manual assignment inside a managed session, printing the outcome.

    Args:
        isin: ISIN selector.
        security_id: Primary-key selector.
        assignment: The validated assignment to write.
        classified_by: Operator recorded in provenance.
        force: Override a locked row when ``True``.

    Raises:
        click.ClickException: If the row is locked and ``force`` is not set, or
            no security matches the selector.
        Exception: Any other error from the write or commit, re-raised after the
            transaction is rolled back.
    """
    engine = create_db_engine()
    session = get_session_factory(engine)()
    try:
        sec = _find_security(session, isin, security_id)
        apply_manual_classification(
            session, sec, assignment, classified_by=classified_by, force=force
        )
        session.commit()
        click.echo(
            f"Classified {sec.isin or sec.id}: "
            f"{assignment.kind.value}={assignment.value} (locked)."
        )
    except ClassificationLockedError as exc:
        session.rollback()
        raise click.ClickException(str(exc)) from exc
    except Exception:
        # Roll back any partial write before re-raising (matches import_xml). A
        # commit/flush failure or a taxonomy-resolution error must not leave the
        # transaction to be discarded implicitly by close().
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


@click.group("classify")
def classify() -> None:
    """Manually classify a security (Tier-4) and lock it against overwrite."""


def _selector_options(
    func: Callable[..., None],
) -> Callable[..., None]:
    """Attach the shared selector + provenance options to a subcommand.

    Args:
        func: The click command function to decorate.

    Returns:
        The decorated function with --isin/--id/--classified-by/--force options.
    """
    func = click.option("--isin", default=None, help="Select the security by ISIN.")(
        func
    )
    func = click.option(
        "--id", "security_id", type=int, default=None, help="Select by primary key."
    )(func)
    func = click.option(
        "--classified-by", required=True, help="Operator recorded in provenance."
    )(func)
    return click.option(
        "--force", is_flag=True, default=False, help="Override a locked row."
    )(func)


@classify.command("gics-sector")
@click.argument("sector")
@_selector_options
def classify_gics_sector(
    sector: str,
    isin: str | None,
    security_id: int | None,
    classified_by: str,
    *,
    force: bool,
) -> None:
    """Assign a GICS-L1 SECTOR (validated against the committed taxonomy)."""
    try:
        canonical = resolve_gics_sector(sector)
    except UnknownClassificationValueError as exc:
        raise click.ClickException(str(exc)) from exc
    _run_assignment(
        isin,
        security_id,
        ManualAssignment(AssignmentKind.GICS_SECTOR, canonical),
        classified_by,
        force=force,
    )


@classify.command("sleeve")
@click.argument("brx_key")
@_selector_options
def classify_sleeve(
    brx_key: str,
    isin: str | None,
    security_id: int | None,
    classified_by: str,
    *,
    force: bool,
) -> None:
    """Assign a BRX-Plus sleeve by leaf KEY (e.g. AC.ALTS.CRYPTO.BTC)."""
    try:
        resolve_brx_plus_sleeve(brx_key)
    except UnknownClassificationValueError as exc:
        raise click.ClickException(str(exc)) from exc
    _run_assignment(
        isin,
        security_id,
        ManualAssignment(AssignmentKind.SLEEVE, brx_key),
        classified_by,
        force=force,
    )


@classify.command("cash")
@_selector_options
def classify_cash(
    isin: str | None,
    security_id: int | None,
    classified_by: str,
    *,
    force: bool,
) -> None:
    """Assign the security to the Cash & Cash Equivalents sleeve."""
    _run_assignment(
        isin,
        security_id,
        ManualAssignment(AssignmentKind.CASH, CASH_LEVEL1),
        classified_by,
        force=force,
    )


@classify.command("crypto-seed")
@click.option("--classified-by", required=True, help="Operator recorded in provenance.")
@click.option("--force", is_flag=True, default=False, help="Override locked rows.")
def classify_crypto_seed(classified_by: str, *, force: bool) -> None:
    """Bulk-apply the committed crypto seed to securities matched by symbol."""
    engine = create_db_engine()
    session = get_session_factory(engine)()
    try:
        count = apply_crypto_seed(session, classified_by=classified_by, force=force)
        session.commit()
        click.echo(f"Applied crypto seed to {count} securities.")
    except ValueError as exc:
        # A malformed seed or an unknown BRX-Plus value (both ValueError
        # subclasses) should surface as a clean CLI error, not a raw traceback.
        session.rollback()
        raise click.ClickException(str(exc)) from exc
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


app.add_command(classify)


@app.command("reconcile-positions")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--database-url",
    default=None,
    help="Override database URL. Defaults to DB_* environment variables.",
)
@click.option(
    "--create-schema/--no-create-schema",
    default=False,
    show_default=True,
    help="Create tables before reconciling (useful for a fresh database).",
)
@click.option(
    "--tolerance",
    default=str(DEFAULT_TOLERANCE),
    show_default=True,
    help="Absolute share tolerance for the MATCHED band.",
)
def reconcile_positions_cmd(
    file: str,
    database_url: str | None,
    create_schema: bool,
    tolerance: str,
) -> None:
    """Reconcile reconstructed Layer-1 positions against an IBKR snapshot FILE.

    FILE is an IBKR positions Flex Query XML (the <OpenPosition> snapshot). The
    snapshot is persisted idempotently, then each (account, report_date) it
    contains is reconstructed from Layer-1 share-moving transactions and compared.
    """
    tol = Decimal(tolerance)
    engine = create_db_engine(database_url)
    if create_schema:
        create_tables(engine)

    session = get_session_factory(engine)()
    try:
        summary = IBKRPositionsImportService(session).import_from_file(file)
        scopes = sorted(
            {
                (row.account_number, row.report_date)
                for row in session.query(InteractiveBrokersOpenPosition).filter(
                    InteractiveBrokersOpenPosition.import_batch_id
                    == summary.import_batch_id
                )
            }
        )
        click.echo(
            f"Imported {summary.positions} snapshot row(s) "
            f"(skipped {summary.skipped} existing) as batch {summary.import_batch_id}."
        )
        for account, report_date in scopes:
            rows = reconcile_positions(session, account, report_date, tol)
            click.echo(f"\nAccount {account} as of {report_date}:")
            click.echo(
                f"  {'IDENTIFIER':<16}{'SYMBOL':<10}{'RECONSTRUCTED':>16}"
                f"{'REPORTED':>16}{'DRIFT':>14}  STATUS"
            )
            counts: dict[str, int] = {}
            for r in rows:
                ident = r.isin or r.conid or "?"
                sym = r.symbol or "-"
                reported = "-" if r.reported_qty is None else f"{r.reported_qty}"
                click.echo(
                    f"  {ident:<16}{sym:<10}{r.reconstructed_qty!s:>16}"
                    f"{reported:>16}{r.drift!s:>14}  {r.status}"
                )
                counts[r.status] = counts.get(r.status, 0) + 1
            summary_line = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            click.echo(f"  Summary: {summary_line}")
    finally:
        session.close()


if __name__ == "__main__":
    app()
