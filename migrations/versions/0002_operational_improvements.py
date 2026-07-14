"""Structured data, solution outcomes, versions and audit."""
from alembic import op
import sqlalchemy as sa

revision = "0002_operational"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("location", sa.String(120)))
        batch.add_column(sa.Column("asset_tag", sa.String(80)))
        batch.add_column(sa.Column("device_model", sa.String(120)))
        batch.add_column(sa.Column("issue_type", sa.String(120)))
        batch.add_column(sa.Column("urgency", sa.String(20)))
        batch.add_column(sa.Column("impact", sa.String(20)))
        batch.add_column(sa.Column("rating", sa.Integer()))
        batch.create_index("ix_sessions_issue_type", ["issue_type"])
    with op.batch_alter_table("interactions") as batch:
        batch.add_column(sa.Column("solution_result", sa.String(30)))
        batch.add_column(sa.Column("result_at", sa.DateTime(timezone=True)))
    op.create_table(
        "knowledge_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("change_note", sa.String(500)),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("category", "version_number", name="uq_knowledge_category_version"),
    )
    op.create_index("ix_knowledge_versions_category", "knowledge_versions", ["category"])
    op.create_index("ix_knowledge_versions_status", "knowledge_versions", ["status"])
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(120)),
        sa.Column("details", sa.Text()),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("knowledge_versions")
    with op.batch_alter_table("interactions") as batch:
        batch.drop_column("result_at")
        batch.drop_column("solution_result")
    with op.batch_alter_table("sessions") as batch:
        batch.drop_index("ix_sessions_issue_type")
        for column in ("rating", "impact", "urgency", "issue_type", "device_model", "asset_tag", "location"):
            batch.drop_column(column)
