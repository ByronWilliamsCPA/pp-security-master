"""ibkr non trade records

Adds record_type discriminator + nullable non-trade columns to
transactions_interactive_brokers (IBKR cash, corporate-action, transfer ingest).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "71ab9a687378"  # pragma: allowlist secret
down_revision = "d3a1c0ffee01"
branch_labels = None
depends_on = None

_TABLE = "transactions_interactive_brokers"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column("record_type", sa.String(20), nullable=False, server_default="TRADE"),
    )
    op.add_column(_TABLE, sa.Column("action_id", sa.String(50), nullable=True))
    op.add_column(_TABLE, sa.Column("action_description", sa.Text(), nullable=True))
    op.add_column(_TABLE, sa.Column("direction", sa.String(8), nullable=True))
    op.add_column(_TABLE, sa.Column("dividend_type", sa.String(50), nullable=True))
    op.add_column(_TABLE, sa.Column("ex_date", sa.Date(), nullable=True))
    op.add_column(_TABLE, sa.Column("proceeds", sa.Numeric(18, 6), nullable=True))
    op.add_column(_TABLE, sa.Column("realized_pnl", sa.Numeric(18, 6), nullable=True))
    op.add_column(_TABLE, sa.Column("figi", sa.String(12), nullable=True))
    op.add_column(_TABLE, sa.Column("conid", sa.String(20), nullable=True))
    op.create_index(op.f(f"ix_{_TABLE}_record_type"), _TABLE, ["record_type"])
    op.create_index(op.f(f"ix_{_TABLE}_action_id"), _TABLE, ["action_id"])
    op.create_index(op.f(f"ix_{_TABLE}_figi"), _TABLE, ["figi"])
    # #ASSUME (data integrity): every pre-existing row in this table is a trade,
    # so the server_default backfills record_type="TRADE" correctly for all of them.
    # This holds because non-trade ingest does not exist before this migration.
    # #VERIFY: before relying on the backfill in production, confirm the pre-migration
    # table contains only trade rows (e.g. SELECT DISTINCT record_type after upgrade,
    # or check that every row has a non-null trade_id).
    # Drop the server_default so future inserts rely on the ORM default.
    op.alter_column(_TABLE, "record_type", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f(f"ix_{_TABLE}_figi"), table_name=_TABLE)
    op.drop_index(op.f(f"ix_{_TABLE}_action_id"), table_name=_TABLE)
    op.drop_index(op.f(f"ix_{_TABLE}_record_type"), table_name=_TABLE)
    op.drop_column(_TABLE, "conid")
    op.drop_column(_TABLE, "figi")
    op.drop_column(_TABLE, "realized_pnl")
    op.drop_column(_TABLE, "proceeds")
    op.drop_column(_TABLE, "ex_date")
    op.drop_column(_TABLE, "dividend_type")
    op.drop_column(_TABLE, "direction")
    op.drop_column(_TABLE, "action_description")
    op.drop_column(_TABLE, "action_id")
    op.drop_column(_TABLE, "record_type")
