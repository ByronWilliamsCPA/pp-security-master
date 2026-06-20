# ADR-014: PP XML Import, CLI Framework, and Round-Trip Strategy

**Date**: 2026-06-20  
**Status**: Accepted  
**Deciders**: Byron, Development Team  
**Consulted**: Roadmap 2026-06-19 Phase C  
**Informed**: Storage and Patch layers  

## Context

The repository had a one-directional PP XML exporter (`patch/pp_xml_export.py`)
and storage models, but no importer, no Alembic baseline, and a stub CLI. Phase
C of `docs/project/ROADMAP_2026-06-19.md` calls for a PP XML round-trip walking
skeleton: import a Portfolio Performance `client.xml`, persist it, and export it
back. Several design choices and a few latent defects had to be settled to make
that loop work end to end.

## Decision

1. **XML handling: build with stdlib, parse with defusedxml.** Document
   construction uses `xml.etree.ElementTree` (defusedxml deliberately omits the
   writer API: `Element`/`SubElement`/`tostring`), while all parsing of
   external or generated input uses `defusedxml.ElementTree`. Building XML is
   not a parse-side security risk; parsing untrusted XML is, so the safe parser
   is reserved for that path. This also corrected the exporter, which imported
   `defusedxml.ElementTree` and then called `ET.Element`, a runtime failure that
   no test had previously exercised.

2. **CLI framework: Click, not Typer.** `click>=8.1` is already a project
   dependency; Typer would add a new one for no benefit at this scale. The
   `pp-master` console entry point exposes `import-xml` and `export-xml`.

3. **Importer architecture: parse/persist split.** `parse_client(xml) ->
   ParsedClient` is a pure function (no I/O), unit-testable without a database.
   `PPXMLImportService` maps a `ParsedClient` onto ORM rows. This matters
   because the PP models use PostgreSQL-native `UUID`/`JSON` types that SQLite
   cannot emulate, so without the split every importer test would require a live
   Postgres.

4. **Round-trip scope: backbone first.** The importer loads client config,
   securities with full price history, accounts, portfolios, and bookmarks. The
   transaction graph (`account-transaction`/`portfolio-transaction` with
   `crossEntry` linkage and positional `security[N]` references) is deferred to
   a later Phase C increment. Round-trip fidelity is asserted only for the
   supported subset.

5. **Schema corrections required by real data.** `PPSecurityPrice.price_value`
   is `BigInteger`, not `Integer`: PP stores prices as value * 1e8, so a ~$26
   price overflows a 32-bit integer. The two `PPTransactionUnit` navigation
   relationships are `viewonly=True` to resolve an overlapping-foreign-key
   mapper error on a soft-polymorphic key. Both defects were latent because no
   prior test initialized the mappers against a real database.

## Consequences

- A working vertical slice exists: `alembic upgrade head` then `pp-master
  import-xml` then `pp-master export-xml` round-trips the supported entities on
  the committed 3.4 MB sample (18 securities, 53,207 prices, 3 accounts, 2
  portfolios, 18 bookmarks).
- The transaction graph is the next increment and will reuse the parse/persist
  split. Until then, exported backups omit transactions.
- The importer is idempotent: securities match by ISIN, accounts and portfolios
  by uuid, bookmarks by label and pattern, so re-import does not duplicate rows.
- Alembic migrations live in `sql/versions/` and are excluded from Ruff (they
  are generated code).
