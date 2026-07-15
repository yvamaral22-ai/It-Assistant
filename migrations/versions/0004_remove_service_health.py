"""Remove the manual service health panel."""
from alembic import op
import sqlalchemy as sa

revision = "0004_remove_service_health"
down_revision = "0003_service_health"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("service_health")


def downgrade() -> None:
    op.create_table(
        "service_health",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(300)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("message", sa.String(500)),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_service_health_name", "service_health", ["name"], unique=True)
    op.create_index("ix_service_health_status", "service_health", ["status"])
    op.create_index("ix_service_health_is_active", "service_health", ["is_active"])
