"""add agent tables

Revision ID: a1b2c3d4e5f6
Revises: 3876a7bdd7ff
Create Date: 2026-08-05 00:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "3876a7bdd7ff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maintenance_busy_window",
        sa.Column("warehouse_id", sa.Integer(), nullable=False, comment="所属仓库"),
        sa.Column("weekday", sa.Integer(), nullable=False, comment="星期 0-6"),
        sa.Column("start_time", sa.Time(), nullable=False, comment="时段开始"),
        sa.Column("end_time", sa.Time(), nullable=False, comment="时段结束"),
        sa.Column("busy_level", sa.Integer(), nullable=False, comment="忙闲等级 1=很闲 5=很忙"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, comment="租户ID（预留）"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouse.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_maintenance_busy_window_warehouse_id",
        "maintenance_busy_window",
        ["warehouse_id"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_busy_window_tenant_id",
        "maintenance_busy_window",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "maintenance_plan",
        sa.Column("warehouse_id", sa.Integer(), nullable=False, comment="所属仓库"),
        sa.Column("device_id", sa.Integer(), nullable=False, comment="维保对象设备"),
        sa.Column("plan_date", sa.Date(), nullable=False, comment="计划日期"),
        sa.Column("start_time", sa.Time(), nullable=True, comment="建议开始时间"),
        sa.Column("end_time", sa.Time(), nullable=True, comment="建议结束时间"),
        sa.Column("task_type", sa.String(length=20), nullable=False, comment="作业类型"),
        sa.Column("title", sa.String(length=200), nullable=False, comment="计划标题"),
        sa.Column("reason", sa.Text(), nullable=True, comment="生成依据/原因"),
        sa.Column("status", sa.String(length=20), nullable=False, comment="状态"),
        sa.Column("source", sa.String(length=20), nullable=False, comment="来源"),
        sa.Column("created_by", sa.String(length=50), nullable=True, comment="创建人"),
        sa.Column("work_order_id", sa.Integer(), nullable=True, comment="转工单后的工单 ID"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, comment="租户ID（预留）"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["device.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouse.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_order.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_maintenance_plan_device_id", "maintenance_plan", ["device_id"], unique=False
    )
    op.create_index(
        "ix_maintenance_plan_plan_date", "maintenance_plan", ["plan_date"], unique=False
    )
    op.create_index(
        "ix_maintenance_plan_warehouse_id", "maintenance_plan", ["warehouse_id"], unique=False
    )
    op.create_index(
        "ix_maintenance_plan_tenant_id", "maintenance_plan", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_maintenance_plan_tenant_id", table_name="maintenance_plan")
    op.drop_index("ix_maintenance_plan_warehouse_id", table_name="maintenance_plan")
    op.drop_index("ix_maintenance_plan_plan_date", table_name="maintenance_plan")
    op.drop_index("ix_maintenance_plan_device_id", table_name="maintenance_plan")
    op.drop_table("maintenance_plan")
    op.drop_index("ix_maintenance_busy_window_tenant_id", table_name="maintenance_busy_window")
    op.drop_index("ix_maintenance_busy_window_warehouse_id", table_name="maintenance_busy_window")
    op.drop_table("maintenance_busy_window")
