"""d3 classification provenance and override lock

Revision ID: d3a1c0ffee01
Revises: d90f75a3b03e
Create Date: 2026-06-21 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3a1c0ffee01'  # pragma: allowlist secret -- Alembic revision id, not a secret
down_revision: str | None = 'd90f75a3b03e'  # pragma: allowlist secret -- Alembic revision id, not a secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add provenance + override-lock columns to securities_master."""
    op.add_column('securities_master', sa.Column('classification_tier', sa.Integer(), nullable=True))
    op.add_column('securities_master', sa.Column('classification_source', sa.String(length=50), nullable=True))
    op.add_column('securities_master', sa.Column('classification_confidence', sa.Numeric(precision=3, scale=2), nullable=True))
    op.add_column(
        'securities_master',
        sa.Column('classification_locked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.add_column('securities_master', sa.Column('classified_by', sa.String(length=100), nullable=True))
    op.add_column('securities_master', sa.Column('classified_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Drop the provenance + override-lock columns."""
    op.drop_column('securities_master', 'classified_at')
    op.drop_column('securities_master', 'classified_by')
    op.drop_column('securities_master', 'classification_locked')
    op.drop_column('securities_master', 'classification_confidence')
    op.drop_column('securities_master', 'classification_source')
    op.drop_column('securities_master', 'classification_tier')
