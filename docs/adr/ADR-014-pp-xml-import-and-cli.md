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

6. **Transactions are serialized with XStream references; import the by-value
   ones first.** PP serializes the transaction graph using XStream
   object-identity references: each transaction is written once by value, and
   every later appearance is an empty `reference="..."` pointer. In the sample,
   the first account has 248 `<account-transaction>` slots, but only 2 are real
   definitions; the other 246 are pointers, and the portfolio transactions live
   nested inside the account transactions' `<crossEntry>` blocks. The importer
   parses and persists the by-value account-transactions (with their fee/tax
   units and positional `security[N]` references resolved) and skips the
   pointers. Importing portfolio transactions and reconstructing the cross-entry
   linkage requires a relative-reference resolver (parent map plus `../..` XPath
   interpretation) and is the next increment; for now only `cross_entry_type` is
   recorded.

## Consequences

- A working vertical slice exists: `alembic upgrade head` then `pp-master
  import-xml` then `pp-master export-xml` round-trips the supported entities on
  the committed 3.4 MB sample (18 securities, 53,207 prices, 3 accounts, 2
  portfolios, 18 bookmarks, 2 account-transactions).
- The remaining transaction work is bounded and specified: resolve XStream
  references to import portfolio transactions and link cross-entries. It reuses
  the parse/persist split.
- The importer is idempotent: securities match by ISIN, accounts and portfolios
  by uuid, bookmarks by label and pattern, and account-transactions by uuid, so
  re-import does not duplicate rows.
- Alembic migrations live in `sql/versions/` and are excluded from Ruff (they
  are generated code).
