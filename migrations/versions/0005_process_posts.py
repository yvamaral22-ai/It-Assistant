"""Editable internal process posts."""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0005_process_posts"
down_revision = "0004_remove_service_health"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "process_posts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_process_posts_is_active", "process_posts", ["is_active"])
    posts = sa.table(
        "process_posts",
        sa.column("title", sa.String),
        sa.column("content", sa.Text),
        sa.column("display_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(posts, [
        {
            "title": "Como consigo acesso ao WeChat?",
            "content": (
                "É necessário abrir um chamado na plataforma de atendimento.\n\n"
                "Antes da liberação, a solicitação precisa conter a aprovação "
                "do gestor imediato e do diretor da área."
            ),
            "display_order": 10,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "title": "Preciso de acesso à VPN",
            "content": (
                "É necessário abrir um chamado na plataforma de atendimento.\n\n"
                "A solicitação precisa conter a aprovação do gestor imediato, "
                "do diretor da área e do gestor de Recursos Humanos."
            ),
            "display_order": 20,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
    ])


def downgrade() -> None:
    op.drop_table("process_posts")
