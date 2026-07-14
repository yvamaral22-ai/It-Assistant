"""Initial sessions, interactions and users schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_name", sa.String(120)),
        sa.Column("department", sa.String(120)),
        sa.Column("computer_name", sa.String(120)),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("initial_description", sa.Text()),
        sa.Column("final_feedback", sa.Text()),
        sa.Column("current_node_id", sa.String(100)),
    )
    op.create_index("ix_sessions_category", "sessions", ["category"])
    op.create_index("ix_sessions_status", "sessions", ["status"])
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_table(
        "interactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("node_id", sa.String(100), nullable=False),
        sa.Column("node_type", sa.String(30), nullable=False),
        sa.Column("question_text", sa.Text()),
        sa.Column("selected_value", sa.String(500)),
        sa.Column("selected_label", sa.String(500)),
        sa.Column("displayed_solution", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_interactions_session_id", "interactions", ["session_id"])


def downgrade() -> None:
    op.drop_table("interactions")
    op.drop_table("users")
    op.drop_table("sessions")
