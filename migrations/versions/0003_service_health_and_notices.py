"""Service health cards and internal notices."""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0003_service_health"
down_revision = "0002_operational"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    services = sa.table(
        "service_health",
        sa.column("name", sa.String), sa.column("description", sa.String),
        sa.column("status", sa.String), sa.column("message", sa.String),
        sa.column("display_order", sa.Integer), sa.column("is_active", sa.Boolean),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(services, [
        {"name": "Internet", "description": "Conectividade externa", "status": "unknown", "message": "Aguardando atualização da TI.", "display_order": 10, "is_active": True, "updated_at": now},
        {"name": "E-mail corporativo", "description": "Envio e recebimento de mensagens", "status": "unknown", "message": "Aguardando atualização da TI.", "display_order": 20, "is_active": True, "updated_at": now},
        {"name": "Sistemas corporativos", "description": "Aplicações internas e ERP", "status": "unknown", "message": "Aguardando atualização da TI.", "display_order": 30, "is_active": True, "updated_at": now},
        {"name": "Impressoras", "description": "Serviços de impressão", "status": "unknown", "message": "Aguardando atualização da TI.", "display_order": 40, "is_active": True, "updated_at": now},
    ])
    op.create_table(
        "internal_notices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_internal_notices_severity", "internal_notices", ["severity"])
    op.create_index("ix_internal_notices_is_active", "internal_notices", ["is_active"])


def downgrade() -> None:
    op.drop_table("internal_notices")
    op.drop_table("service_health")
