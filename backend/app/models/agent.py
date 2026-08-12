"""Agent 模块模型：仓库忙闲时段 + AI 维保计划"""

from datetime import date, time

from sqlalchemy import Date, ForeignKey, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import IdMixin, TenantMixin, TimestampMixin


class MaintenanceBusyWindow(IdMixin, TenantMixin, TimestampMixin, Base):
    """仓库忙闲时段（维保错峰依据，busy_level 越小越闲）"""

    __tablename__ = "maintenance_busy_window"

    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse.id"), index=True, comment="所属仓库"
    )
    weekday: Mapped[int] = mapped_column(comment="星期 0-6（周一=0，周日=6）")
    start_time: Mapped[time] = mapped_column(Time, comment="时段开始")
    end_time: Mapped[time] = mapped_column(Time, comment="时段结束")
    busy_level: Mapped[int] = mapped_column(comment="忙闲等级 1=很闲 5=很忙")


class MaintenancePlan(IdMixin, TenantMixin, TimestampMixin, Base):
    """AI 维保计划（Agent 生成，可转工单）"""

    __tablename__ = "maintenance_plan"

    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse.id"), index=True, comment="所属仓库"
    )
    device_id: Mapped[int] = mapped_column(
        ForeignKey("device.id"), index=True, comment="维保对象设备"
    )
    plan_date: Mapped[date] = mapped_column(Date, index=True, comment="计划日期")
    start_time: Mapped[time | None] = mapped_column(Time, comment="建议开始时间")
    end_time: Mapped[time | None] = mapped_column(Time, comment="建议结束时间")
    task_type: Mapped[str] = mapped_column(
        String(20), default="MAINTAIN", comment="作业类型: INSPECT/MAINTAIN/REPAIR"
    )
    title: Mapped[str] = mapped_column(String(200), comment="计划标题")
    reason: Mapped[str | None] = mapped_column(Text, comment="生成依据/原因")
    status: Mapped[str] = mapped_column(
        String(20), default="DRAFT", comment="状态: DRAFT/CONFIRMED/EXECUTED/CANCELLED"
    )
    source: Mapped[str] = mapped_column(String(20), default="AGENT", comment="来源")
    created_by: Mapped[str | None] = mapped_column(String(50), comment="创建人")
    work_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("work_order.id"), comment="转工单后的工单 ID"
    )
