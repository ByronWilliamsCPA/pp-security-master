"""account balances

Adds the account_balances ledger: one row per account per as-of date, written
by the nightly IBKR totals job and by manual marks. entity_id is a required
UUID with no foreign key because the entity master lives outside this database.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = (
    "a1c4e7b90d21"  # pragma: allowlist secret -- Alembic revision id, not a secret
)
down_revision = (
    "c5f2d80b6e37"  # pragma: allowlist secret -- Alembic revision id, not a secret
)
branch_labels = None
depends_on = None

_TABLE = "account_balances"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_key", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("value", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("entered_by", sa.String(100), nullable=False),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "account_key", "as_of", name="uq_account_balances_key_as_of"
        ),
        sa.CheckConstraint(
            "substr(account_key, 1, 3) = 'pp:'",
            name="ck_account_balances_key_prefix",
        ),
        sa.CheckConstraint(
            "category IN ('Investments', 'Retirement', 'Cash', "
            "'Digital currency', 'Alternatives')",
            name="ck_account_balances_category",
        ),
        sa.CheckConstraint("length(currency) = 3", name="ck_account_balances_currency"),
    )
    op.create_index(op.f(f"ix_{_TABLE}_account_key"), _TABLE, ["account_key"])
    op.create_index(op.f(f"ix_{_TABLE}_entity_id"), _TABLE, ["entity_id"])
    op.create_index(op.f(f"ix_{_TABLE}_as_of"), _TABLE, ["as_of"])


def downgrade() -> None:
    # #CRITICAL (data integrity): ibkr_flex rows can be recomputed from the
    # broker tables, but manual marks (manual_mark and feed sources) cannot.
    # Refuse to drop the table while any exist so a downgrade never silently
    # destroys hand-entered statement values.
    # #VERIFY: export or delete the non-ibkr_flex rows deliberately, then
    # re-run the downgrade.
    if not context.is_offline_mode():
        manual_rows = (
            op.get_bind()
            .execute(
                sa.text(
                    "SELECT count(*) FROM account_balances WHERE source <> 'ibkr_flex'"
                )
            )
            .scalar_one()
        )
        if manual_rows:
            msg = (
                f"{_TABLE} holds {manual_rows} row(s) that cannot be regenerated "
                "(source is not ibkr_flex); export or delete them before "
                "downgrading"
            )
            raise RuntimeError(msg)
    op.drop_index(op.f(f"ix_{_TABLE}_as_of"), table_name=_TABLE)
    op.drop_index(op.f(f"ix_{_TABLE}_entity_id"), table_name=_TABLE)
    op.drop_index(op.f(f"ix_{_TABLE}_account_key"), table_name=_TABLE)
    op.drop_table(_TABLE)
