"""Índices de prefijo literal sobre lower(apellido); conserva tabla e índice previo."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    for part in ("paterno", "materno"):
        op.create_index(
            f"ix_patients_{part}_prefix", "patients",
            [sa.text(f"lower(apellido_{part}) text_pattern_ops")],
        )


def downgrade():
    for part in ("paterno", "materno"):
        op.drop_index(f"ix_patients_{part}_prefix", table_name="patients")
