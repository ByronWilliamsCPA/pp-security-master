"""Command-line interface for the Security Master service.

Exposes three commands under the ``pp-master`` group:

- ``import-xml`` / ``export-xml``: move a Portfolio Performance ``client.xml``
  backup in and out of the database.
- ``import-broker``: ingest a broker export (currently IBKR Flex Query XML) into
  the transactions store.

Database connection details are read from the environment (see
:func:`security_master.storage.database.get_database_url`).
"""

from __future__ import annotations

import click

from security_master.extractor import IBKRFlexImportService
from security_master.patch.pp_xml_export import PPXMLExportService
from security_master.patch.pp_xml_import import PPXMLImportService
from security_master.storage.database import (
    create_db_engine,
    create_tables,
    get_session_factory,
)

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
        f"Imported {summary.trades} trade(s) "
        f"(skipped {summary.skipped} existing) "
        f"from {file} as batch {summary.import_batch_id}."
    )


if __name__ == "__main__":
    app()
