# ADR-017: Account Balances Ledger and Nightly Totals

**Date**: 2026-09-30
**Status**: Proposed (pending owner acceptance; see Relationship to ADR-016)
**Deciders**: Development Team
**Consulted**: ADR-014 (PP XML Import and CLI), ADR-016 (Crosswalk Architecture and IBOR/ABOR Navigation)
**Informed**: Storage, Extractor, and CLI layers; downstream readers of `account_balances`

## Context

The service holds positions per broker account but has no single, dated answer
to "what is this account worth on this date". Two gaps prevent one:

1. A brokerage total built from `ibkr_open_positions.position_value` alone is
   short by the account's cash balance, because the Flex position snapshot
   carries securities only.
2. Some accounts have no broker feed at all. Their value is a statement figure
   typed in by a person, and the record must say who entered it and when.

Other services will read the resulting rows, so the column contract has to be
stable and enforced in the database, not left to convention.

## Decision

### 1. One ledger table, `account_balances`

One row per account per as-of date, unique on `(account_key, as_of)`. Columns:
account key, display name, `entity_id` (UUID, never null), category, source,
`value` `Numeric(18, 2)`, `currency`, `as_of`, `entered_by`, `entered_at`, and a
free-text `note`. CHECK constraints pin the `pp:` key prefix, the five-value
category vocabulary, and a three-character currency.

Field rules (also enforced in `security_master.balances.rules`):

- **Account key**: stable, unique, prefixed `pp:` (for example `pp:ibkr:0001`).
  Never a full account number: at most the last four digits, and any run of
  five digits is rejected. IBKR keys are derived as `pp:ibkr:<last four>`.
- **Category**: exactly one of `Investments`, `Retirement`, `Cash`,
  `Digital currency`, `Alternatives`.
- **Source**: `ibkr_flex`, `manual_mark`, or a feed name such as `simplefin` or
  `plaid`.
- **Value**: market value in `currency`; negative only for overdrafts, which
  are accepted for `Cash` accounts only. Numeric at every layer and serialized
  as a two-place decimal string (`"1234.56"`), never a float.
- **Currency**: its own column. The MVP is USD only.
- Balances and account numbers never appear in log lines or error messages.

### 2. IBKR Flex CashReport gets its own table

`ibkr_cash_report` stores ending cash per account, report date, and currency,
unique on that triple. The existing Flex import parses the `CashReport`
section alongside trades, cash transactions, corporate actions, and transfers.
The base-currency roll-up row IBKR appends (`BASE_SUMMARY`) is dropped because
it would double count the per-currency rows.

- Each row is validated before it is stored: a three-letter currency code,
  at most six decimal places, and an absolute value below 10^12. A malformed
  row fails the whole file with a message that names the row but never its
  amount or account number, and nothing from that file is saved.
- Re-importing the same file stores nothing new. If a later file carries a
  different ending cash for the same account, date, and currency (a broker
  restatement), the stored row is updated in place and a warning is logged
  with the date and currency only. A single file that lists the same triple
  twice with different amounts is refused.

### 3. Nightly totals (`pp-master nightly-totals`)

For the latest `ibkr_open_positions.report_date`, per account, sum
`position_value` plus USD ending cash with `Decimal` and write one
`account_balances` row with source `ibkr_flex` and `as_of = report_date`.

Cash joins positions on the exact report date. The expected sequence is to
import every Flex file for a day (positions and the CashReport section) and
then run `nightly-totals`; cash dated a day later or earlier does not join.

- Addition runs in a 60-digit context, so no intermediate sum is rounded; the
  only rounding is one half-up quantization to cents at the end.
- An account whose total cannot be computed exactly is withheld, not written
  short. Each logs one line with the account key and a reason code. The codes
  are:
  - `bad_account_number`: no key can be derived from the broker account
    number.
  - `ambiguous_suffix`: two account numbers share a last-four suffix on any
    date in either table.
  - `unmapped`: the derived key is not in the account registry.
  - `no_rows_on_report_date`: a registered IBKR account has no position or
    cash row on the report date.
  - `missing_value` and `invalid_value`: a value is absent or not finite.
  - `non_usd_row`: a non-USD row with a non-zero amount (non-USD rows are
    never converted).
  - `account_withheld`: the account had a row-level problem.
  - `no_usd_cash_row`: no USD cash row for that account on the report date.
  - `out_of_range`: the total does not fit the column.
  - `negative_total`: a negative total on a non-`Cash` account.
  - `existing_other_source`: a row from a different source already exists
    for that account and date.
- A run-level `cash_date_ahead` rejection is raised when the newest cash
  report is dated after the newest position snapshot, so a missed positions
  import is not silently totalled against stale positions.
- A zero-valued non-USD row contributes nothing, so it is logged and dropped
  without withholding the account.
- Re-running for the same date updates the `ibkr_flex` row in place; it never
  overwrites a row from another source.
- The command exits non-zero when any account was withheld, so a scheduler
  notices.

### 4. Manual marks (`pp-master balance set` and `balance list`)

`balance set --account ... --value ... --as-of ... --source manual_mark
--note ...` records a statement figure. `as_of` is the statement date and may
not be in the future. `--entered-by` records who entered the mark and defaults
to the OS user name; an empty attribution is refused. A second mark for the
same account and date is refused unless `--replace` is passed, and a replace
updates the attribution and timestamp. A replace never overwrites an
`ibkr_flex` total: the broker import is corrected instead. Values are parsed as plain decimals with
at most two places; `1e3`, `NaN`, and thousands separators are rejected, and
the offending text is never echoed. `ibkr_flex` is not an allowed manual source. The attribution and note may
not contain control characters (the note may contain line breaks and tabs).
The service applies the same rules as the CLI, so other callers cannot bypass
them. Database errors are reported without SQL parameters, and the engine is
created with `hide_parameters=True` so values never reach a traceback.

`balance list` prints every mapped account with its latest row (or the row for
one `--as-of` date), values as decimal strings, in table or JSON form. A
listed row reports the display name, entity, and category recorded on that
row, so a later registry edit does not rewrite history. Accounts with no row
are still listed, with registry values and empty balance fields.

### 5. Account registry from a seed file, not a table

A YAML seed maps each account key to an entity UUID, a plain-English display
name, and a category. Its path comes from `PP_ACCOUNT_REGISTRY_PATH`
(environment or `.env`) and the file lives outside this repository. Only a
made-up example ships, at `seeds/account_registry.example.yaml`, and stray
`account_registry*.yaml` and `account_registry*.yml` files are gitignored. The
registry is validated as it loads: keys and categories follow the field rules,
the entity UUID may not be the nil UUID, display names are non-empty and at
most 200 characters, and keys are unique.

`legal_entities` and `account_mappings` were considered and not reused.
`legal_entities` has integer keys and no UUID or account key, and
`account_mappings` maps broker account numbers to Portfolio Performance
groups. The entity UUID belongs to an entity master owned elsewhere, so
`account_balances.entity_id` is a bare UUID with no foreign key. Mirroring the
seed into a table here would create a second entity master.

Personal accounts point at the owner's `individual` entity and joint items at a
`household` entity; that choice is made in the seed.

### 6. Relationship to ADR-016

ADR-016 section 3 describes a canonical Entity Registry owned by this service
(the IBOR). This ADR instead treats the entity UUID as owned by an external
entity master and keeps only a seed file here. The two are compatible only if
the external master is the source of the UUIDs that ADR-016's registry would
hold, or if ADR-016's registry is later populated from it.

Open question for the owner: which system owns entity identity. Until that is
decided this ADR stays Proposed. If this service is confirmed as the owner,
`account_balances.entity_id` should gain a foreign key to the ADR-016
registry once that table exists, and the seed file becomes an import into it.

### 7. Migrations

Two Alembic revisions add `ibkr_cash_report` (`c5f2d80b6e37`) and
`account_balances` (`a1c4e7b90d21`). Downgrading `account_balances` refuses to
run while it holds any row whose source is not `ibkr_flex`, because manual
marks cannot be recreated from broker files. Back up the table and clear those
rows first if the downgrade is intended. In offline (SQL script) mode the
check cannot run and the drop is emitted as written.

## Consequences

- Positive: one dated, attributable total per account, exact to the cent, with
  a database-level contract for readers.
- Positive: real entity identifiers and account structure never enter the
  repository.
- Negative: SQLite-backed tests store `Numeric` through floats, so the DB-level
  tests use values within double precision; exactness is proven separately on
  the pure summation function with a property test against an integer oracle.
- Negative: multi-currency accounts are withheld until a conversion decision is
  made; nothing here converts.

## Risks and Assumptions

- #ASSUME (external resource): the Flex `CashReportCurrency` element exposes
  `accountId`, `currency`, `endingCash`, and `toDate` (or `reportDate`), and the
  cash report date matches the position snapshot date.
  #VERIFY against a real CashReport export before the first production run.
- #ASSUME (financial): `endingCash` is the figure that completes the positions
  total. #VERIFY the first nightly total against the broker statement.
- #EDGE (data integrity): two accounts sharing a last-four suffix are rejected
  rather than merged. #VERIFY the seed contains no colliding suffixes.
