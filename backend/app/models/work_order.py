"""工单域模型：维保工单 + 工单备件消耗明细"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import IdMixin, TenantMixin, TimestampMixin


class WorkOrder(IdMixin, TenantMixin, TimestampMixin, Base):
    """维保工单（发起-派单-执行-验收-归档全流程）"""

    __tablename__ = "work_order"

    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse.id"), index=True, comment="仓库"
    )
    device_id: Mapped[int] = mapped_column(ForeignKey("device.id"), index=True, comment="设备")
    order_no: Mapped[str] = mapped_column(String(50), unique=True, comment="工单编号")
    title: Mapped[str] = mapped_column(String(200), comment="工单标题")
    description: Mapped[str | None] = mapped_column(Text, comment="问题描述")
    order_type: Mapped[str] = mapped_column(
        String(20),
        default="MAINTENANCE",
        comment="类型: REPAIR/MAINTENANCE/INSPECTION/OTHER",
    )
    source: Mapped[str] = mapped_column(
        String(20), default="MANUAL", comment="来源: ALERT/PLAN/MANUAL"
    )
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alert.id"), comment="来源预警（可空）")
    priority: Mapped[str] = mapped_column(
        String(20),
        default="MEDIUM",
        index=True,
        comment="优先级: LOW/MEDIUM/HIGH/URGENT",
    )
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"), comment="指派人")
    status: Mapped[str] = mapped_column(
        String(30),
        default="PENDING_ASSIGN",
        index=True,
        comment="状态: PENDING_ASSIGN/PENDING_EXECUTE/IN_PROGRESS/PENDING_ACCEPT/COMPLETED/CANCELLED",
    )
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime, comment="计划开始")
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime, comment="计划结束")
    actual_start: Mapped[datetime | None] = mapped_column(DateTime, comment="实际开始")
    actual_end: Mapped[datetime | None] = mapped_column(DateTime, comment="实际结束")
    result: Mapped[str | None] = mapped_column(Text, comment="处理结果")
    created_by: Mapped[str | None] = mapped_column(String(50), comment="创建人")


class WorkOrderPart(IdMixin, TenantMixin, TimestampMixin, Base):
    """工单-备件消耗明细（工单完成后自动扣库存）"""

    __tablename__ = "work_order_part"

    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_order.id"), index=True, comment="工单"
    )
    spare_part_id: Mapped[int] = mapped_column(ForeignKey("spare_part.id"), comment="备件")
    quantity: Mapped[int] = mapped_column(Integer, default=1, comment="数量")
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), comment="单价")
