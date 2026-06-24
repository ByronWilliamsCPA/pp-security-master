"""account mappings and consolidated source unique constraint

Adds the account_mappings table (broker account -> PP group/account) and the
uq_consolidated_source unique constraint on transactions_consolidated, the
Layer-2 idempotency key for the L1->L2 normalizer (SP3).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "2a08a665e4e1"  # pragma: allowlist secret -- Alembic revision id, not a secret
down_revision = "32b7a96122d0"  # pragma: allowlist secret -- Alembic revision id, not a secret
branch_labels = None
depends_on = None

_TABLE = "account_mappings"
_UQ = "uq_consolidated_source"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_number", sa.String(50), nullable=False),
        sa.Column("pp_group", sa.String(100), nullable=False),
        sa.Column("pp_account", sa.String(100), nullable=False),
        sa.Column(
            "legal_entity_id",
            sa.Integer(),
            sa.ForeignKey("legal_entities.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        op.f(f"ix_{_TABLE}_account_number"), _TABLE, ["account_number"], unique=True
    )
    op.create_unique_constraint(
        _UQ,
        "transactions_consolidated",
        ["source_table", "source_transaction_id"],
    )


def downgrade() -> None:
    op.drop_constraint(_UQ, "transactions_consolidated", type_="unique")
    op.drop_index(op.f(f"ix_{_TABLE}_account_number"), table_name=_TABLE)
    op.drop_table(_TABLE)
