"""add fusion_diagnosis

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-05 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fusion_diagnosis",
        sa.Column("device_id", sa.Integer(), nullable=False, comment="诊断对象设备"),
        sa.Column("fault_type", sa.String(length=30), nullable=False, comment="故障模式"),
        sa.Column("confidence", sa.Float(), nullable=False, comment="置信度 0-1"),
        sa.Column("signals_json", sa.JSON(), nullable=True, comment="各信号证据"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, comment="租户ID（预留）"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["device.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fusion_diagnosis_device_id", "fusion_diagnosis", ["device_id"], unique=False)
    op.create_index(
        "ix_fusion_diagnosis_fault_type", "fusion_diagnosis", ["fault_type"], unique=False
    )
    op.create_index("ix_fusion_diagnosis_tenant_id", "fusion_diagnosis", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_fusion_diagnosis_tenant_id", table_name="fusion_diagnosis")
    op.drop_index("ix_fusion_diagnosis_fault_type", table_name="fusion_diagnosis")
    op.drop_index("ix_fusion_diagnosis_device_id", table_name="fusion_diagnosis")
    op.drop_table("fusion_diagnosis")
