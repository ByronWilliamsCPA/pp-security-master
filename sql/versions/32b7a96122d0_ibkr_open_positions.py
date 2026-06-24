"""ibkr open positions

Adds the ibkr_open_positions snapshot table and the
v_ibkr_position_reconciliation reporting view (SP2 position reconciliation).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "32b7a96122d0"  # pragma: allowlist secret
down_revision = "71ab9a687378"
branch_labels = None
depends_on = None

_TABLE = "ibkr_open_positions"
_VIEW = "v_ibkr_position_reconciliation"

# The view reconstructs net share quantity from Layer-1 share-moving records and
# joins it to the persisted snapshot per (account, report_date, key).
# #ASSUME (external resource): this view targets PostgreSQL, where the migration
# runs; it is never created in the SQLite test schema (built from Base.metadata,
# not migrations), so the native FULL OUTER JOIN is used and the view itself is
# unexercised by the SQLite test suite. The Python reconcile_positions() path is
# the authoritative, unit-tested implementation.
# #VERIFY: PostgreSQL parity is confirmed manually per the PR test plan
# (alembic upgrade head, then query v_ibkr_position_reconciliation).
# #EDGE (data integrity): COALESCE(SUM(quantity), 0) and the NOT-NULL sec_key
# guard below keep this view aligned with the Python path, which coerces a NULL
# quantity to 0 and skips rows whose isin and conid are both NULL.
# #ASSUME (financial): status uses the DEFAULT tolerance (0.0001 shares); the CLI
# re-derives status with a configurable tolerance from the raw drift.
# #VERIFY: test_drift_at_tolerance_boundary_and_configurable_tolerance.
_VIEW_SQL = f"""
CREATE VIEW {_VIEW} AS
WITH scopes AS (
    SELECT DISTINCT account_number, report_date FROM {_TABLE}
),
recon AS (
    SELECT
        s.account_number AS account_number,
        s.report_date AS report_date,
        COALESCE(t.isin, t.conid) AS sec_key,
        COALESCE(SUM(t.quantity), 0) AS reconstructed_qty
    FROM scopes s
    JOIN transactions_interactive_brokers t
        ON t.account_number = s.account_number
        AND t.record_type IN ('TRADE', 'CORP_ACTION', 'TRANSFER')
        AND t.transaction_date <= s.report_date
        AND COALESCE(t.isin, t.conid) IS NOT NULL
    GROUP BY s.account_number, s.report_date, COALESCE(t.isin, t.conid)
),
snap AS (
    SELECT
        account_number,
        report_date,
        COALESCE(isin, conid) AS sec_key,
        isin,
        conid,
        symbol,
        position AS reported_qty
    FROM {_TABLE}
)
SELECT
    COALESCE(r.account_number, s.account_number) AS account_number,
    COALESCE(r.report_date, s.report_date) AS report_date,
    s.isin AS isin,
    s.conid AS conid,
    s.symbol AS symbol,
    COALESCE(r.sec_key, s.sec_key) AS sec_key,
    COALESCE(r.reconstructed_qty, 0) AS reconstructed_qty,
    s.reported_qty AS reported_qty,
    COALESCE(r.reconstructed_qty, 0) - COALESCE(s.reported_qty, 0) AS drift,
    CASE
        WHEN s.reported_qty IS NULL
             AND ABS(COALESCE(r.reconstructed_qty, 0)) <= 0.0001 THEN 'MATCHED'
        WHEN s.reported_qty IS NULL THEN 'RECONSTRUCTED_ONLY'
        WHEN r.reconstructed_qty IS NULL THEN 'REPORTED_ONLY'
        WHEN ABS(r.reconstructed_qty - s.reported_qty) <= 0.0001 THEN 'MATCHED'
        ELSE 'DRIFT'
    END AS status
FROM recon r
FULL OUTER JOIN snap s
    ON r.account_number = s.account_number
    AND r.report_date = s.report_date
    AND r.sec_key = s.sec_key
"""


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_number", sa.String(50), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("security_name", sa.String(255), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=True),
        sa.Column("isin", sa.String(12), nullable=True),
        sa.Column("cusip", sa.String(9), nullable=True),
        sa.Column("position", sa.Numeric(18, 8), nullable=False),
        sa.Column("position_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("import_batch_id", sa.String(50), nullable=False),
        sa.Column("source_file", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("conid", sa.String(20), nullable=False),
        sa.Column("figi", sa.String(12), nullable=True),
        sa.Column("mark_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("cost_basis_money", sa.Numeric(18, 6), nullable=True),
        sa.Column("cost_basis_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("asset_class", sa.String(20), nullable=True),
        sa.Column("sub_category", sa.String(20), nullable=True),
        sa.Column("side", sa.String(8), nullable=True),
        sa.UniqueConstraint(
            "account_number",
            "report_date",
            "conid",
            name="uq_ibkr_open_positions_acct_date_conid",
        ),
    )
    op.create_index(op.f(f"ix_{_TABLE}_account_number"), _TABLE, ["account_number"])
    op.create_index(op.f(f"ix_{_TABLE}_report_date"), _TABLE, ["report_date"])
    op.create_index(op.f(f"ix_{_TABLE}_symbol"), _TABLE, ["symbol"])
    op.create_index(op.f(f"ix_{_TABLE}_isin"), _TABLE, ["isin"])
    op.create_index(op.f(f"ix_{_TABLE}_import_batch_id"), _TABLE, ["import_batch_id"])
    op.create_index(op.f(f"ix_{_TABLE}_conid"), _TABLE, ["conid"])
    op.create_index(op.f(f"ix_{_TABLE}_figi"), _TABLE, ["figi"])
    op.execute(_VIEW_SQL)


def downgrade() -> None:
    op.execute(f"DROP VIEW IF EXISTS {_VIEW}")
    op.drop_index(op.f(f"ix_{_TABLE}_figi"), table_name=_TABLE)
    op.drop_index(op.f(f"ix_{_TABLE}_conid"), table_name=_TABLE)
    op.drop_index(op.f(f"ix_{_TABLE}_import_batch_id"), table_name=_TABLE)
    op.drop_index(op.f(f"ix_{_TABLE}_isin"), table_name=_TABLE)
    op.drop_index(op.f(f"ix_{_TABLE}_symbol"), table_name=_TABLE)
    op.drop_index(op.f(f"ix_{_TABLE}_report_date"), table_name=_TABLE)
    op.drop_index(op.f(f"ix_{_TABLE}_account_number"), table_name=_TABLE)
    op.drop_table(_TABLE)
