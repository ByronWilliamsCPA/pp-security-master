"""ibkr cash report

Adds the ibkr_cash_report table holding Flex CashReport ending cash per account,
report date, and currency. Needed so a brokerage total is positions plus cash.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = (
    "c5f2d80b6e37"  # pragma: allowlist secret -- Alembic revision id, not a secret
)
down_revision = (
    "2a08a665e4e1"  # pragma: allowlist secret -- Alembic revision id, not a secret
)
branch_labels = None
depends_on = None

_TABLE = "ibkr_cash_report"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_number", sa.String(50), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("ending_cash", sa.Numeric(18, 6), nullable=False),
        sa.Column("import_batch_id", sa.String(50), nullable=False),
        sa.Column("source_file", sa.String(255), nullable=True),
        # Naive UTC, set by the ORM (no server default, which would use the
        # database server's local time zone).
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "account_number",
            "report_date",
            "currency",
            name="uq_ibkr_cash_report_acct_date_ccy",
        ),
    )
    op.create_index(op.f(f"ix_{_TABLE}_account_number"), _TABLE, ["account_number"])
    op.create_index(op.f(f"ix_{_TABLE}_report_date"), _TABLE, ["report_date"])
    op.create_index(op.f(f"ix_{_TABLE}_import_batch_id"), _TABLE, ["import_batch_id"])


def downgrade() -> None:
    op.drop_index(op.f(f"ix_{_TABLE}_import_batch_id"), table_name=_TABLE)
    op.drop_index(op.f(f"ix_{_TABLE}_report_date"), table_name=_TABLE)
    op.drop_index(op.f(f"ix_{_TABLE}_account_number"), table_name=_TABLE)
    op.drop_table(_TABLE)
