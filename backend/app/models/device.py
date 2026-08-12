"""设备域模型：设备台账、传感器点位、类型阈值模板、维保记录"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Float, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import IdMixin, TenantMixin, TimestampMixin


class Device(IdMixin, TenantMixin, TimestampMixin, Base):
    """设备台账（全生命周期档案锚点）"""

    __tablename__ = "device"

    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse.id"), index=True, comment="所属仓库"
    )
    device_code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, comment="设备编号"
    )
    name: Mapped[str] = mapped_column(String(100), comment="设备名称")
    device_type: Mapped[str] = mapped_column(
        String(30),
        index=True,
        comment="设备类型: CONVEYOR/STACKER/AGV/SORTER/FORKLIFT",
    )
    brand: Mapped[str | None] = mapped_column(String(50), comment="品牌")
    model: Mapped[str | None] = mapped_column(String(50), comment="型号")
    location: Mapped[str | None] = mapped_column(String(100), comment="安装位置")
    status: Mapped[str] = mapped_column(
        String(20),
        default="RUNNING",
        index=True,
        comment="状态: RUNNING/STOPPED/MAINTENANCE/SCRAPPED",
    )
    purchase_date: Mapped[date | None] = mapped_column(Date, comment="采购日期")
    install_date: Mapped[date | None] = mapped_column(Date, comment="安装日期")
    scrap_date: Mapped[date | None] = mapped_column(Date, comment="报废日期")
    lifespan_years: Mapped[int | None] = mapped_column(comment="设计寿命（年）")
    supplier: Mapped[str | None] = mapped_column(String(100), comment="供应商")
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), comment="采购价格")
    description: Mapped[str | None] = mapped_column(Text, comment="备注")

    # 关联点位（设备删除时级联删除点位）
    points: Mapped[list["DevicePoint"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )


class DevicePoint(IdMixin, TenantMixin, TimestampMixin, Base):
    """传感器点位（一台设备可挂多个采集点）"""

    __tablename__ = "device_point"
    __table_args__ = (UniqueConstraint("device_id", "point_code", name="uq_device_point_code"),)

    device_id: Mapped[int] = mapped_column(ForeignKey("device.id"), index=True, comment="所属设备")
    point_code: Mapped[str] = mapped_column(String(50), comment="点位编号")
    point_type: Mapped[str] = mapped_column(
        String(20),
        index=True,
        comment="点位类型: VIBRATION/TEMPERATURE/CURRENT",
    )
    unit: Mapped[str | None] = mapped_column(String(20), comment="单位")
    alarm_low: Mapped[float | None] = mapped_column(Float, comment="报警下限")
    alarm_high: Mapped[float | None] = mapped_column(Float, comment="报警上限")
    trend_window: Mapped[int] = mapped_column(default=30, comment="趋势检测窗口（采样点数）")
    trend_delta: Mapped[float] = mapped_column(default=8.0, comment="趋势检测上升幅度阈值")
    collect_interval_seconds: Mapped[int] = mapped_column(default=60, comment="采集频率（秒）")
    enabled: Mapped[bool] = mapped_column(default=True, comment="是否启用")

    device: Mapped["Device"] = relationship(back_populates="points")


class DeviceTypeThreshold(IdMixin, TimestampMixin, Base):
    """设备类型阈值模板：新设备建档时自动带出初值，点位可覆盖"""

    __tablename__ = "device_type_threshold"
    __table_args__ = (UniqueConstraint("device_type", "point_type", name="uq_type_point"),)

    device_type: Mapped[str] = mapped_column(String(30), index=True, comment="设备类型")
    point_type: Mapped[str] = mapped_column(String(20), comment="点位类型")
    unit: Mapped[str | None] = mapped_column(String(20), comment="单位")
    alarm_low_default: Mapped[float | None] = mapped_column(Float, comment="默认报警下限")
    alarm_high_default: Mapped[float | None] = mapped_column(Float, comment="默认报警上限")
    trend_window_default: Mapped[int] = mapped_column(
        default=30, comment="默认趋势窗口（采样点数）"
    )
    trend_delta_default: Mapped[float] = mapped_column(default=8.0, comment="默认趋势上升幅度阈值")
    collect_interval_seconds_default: Mapped[int] = mapped_column(
        default=60, comment="默认采集频率（秒）"
    )


class MaintenanceRecord(IdMixin, TenantMixin, TimestampMixin, Base):
    """维保记录（设备台账回写）"""

    __tablename__ = "maintenance_record"

    device_id: Mapped[int] = mapped_column(ForeignKey("device.id"), index=True, comment="设备")
    work_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("work_order.id"), comment="来源工单（可空）"
    )
    maintenance_type: Mapped[str] = mapped_column(
        String(20), comment="维保类型: REPAIR/MAINTENANCE/INSPECTION"
    )
    description: Mapped[str | None] = mapped_column(Text, comment="维保内容")
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), comment="费用")
    executed_by: Mapped[str | None] = mapped_column(String(50), comment="执行人")
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="执行时间")
    next_due_date: Mapped[date | None] = mapped_column(Date, comment="下次保养日期")
