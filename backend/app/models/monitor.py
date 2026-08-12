"""监测域模型：运行数据、健康度快照、预警"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import IdMixin, TenantMixin, TimestampMixin


class SensorData(IdMixin, TenantMixin, Base):
    """运行数据（时序大表，MVP 单表 + 联合索引）"""

    __tablename__ = "sensor_data"
    __table_args__ = (
        Index("idx_point_time", "device_point_id", "collected_at"),
        Index("idx_device_time", "device_id", "collected_at"),
    )

    device_id: Mapped[int] = mapped_column(
        ForeignKey("device.id"), index=True, comment="设备（冗余，加速按设备查询）"
    )
    device_point_id: Mapped[int] = mapped_column(ForeignKey("device_point.id"), comment="采集点位")
    value: Mapped[float] = mapped_column(Float, comment="采集值")
    status: Mapped[str] = mapped_column(
        String(20), default="NORMAL", comment="数据状态: NORMAL/MISSING/ABNORMAL"
    )
    collected_at: Mapped[datetime] = mapped_column(DateTime, index=True, comment="采集时间")


class HealthRecord(IdMixin, TenantMixin, TimestampMixin, Base):
    """设备健康度快照（趋势图数据源）"""

    __tablename__ = "health_record"
    __table_args__ = (Index("idx_device_computed", "device_id", "computed_at"),)

    device_id: Mapped[int] = mapped_column(ForeignKey("device.id"), index=True, comment="设备")
    score: Mapped[float] = mapped_column(Float, comment="健康度评分 0-100")
    level: Mapped[str] = mapped_column(String(20), comment="等级: HEALTHY/SUB_HEALTHY/ABNORMAL")
    factor_json: Mapped[dict | None] = mapped_column(JSON, comment="影响因素（哪些点位/扣分原因）")
    computed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, comment="计算时间"
    )


class Alert(IdMixin, TenantMixin, TimestampMixin, Base):
    """预警/隐患记录（证据链完整：哪层触发、什么值、什么阈值）"""

    __tablename__ = "alert"

    device_id: Mapped[int] = mapped_column(ForeignKey("device.id"), index=True, comment="设备")
    point_id: Mapped[int | None] = mapped_column(
        ForeignKey("device_point.id"), comment="点位（数据链路告警可空）"
    )
    alert_type: Mapped[str] = mapped_column(
        String(30),
        index=True,
        comment="类型: THRESHOLD_HIGH/THRESHOLD_LOW/TREND/ANOMALY/DATA_LINK",
    )
    trigger_layer: Mapped[str] = mapped_column(
        String(30),
        default="THRESHOLD",
        comment="触发层: THRESHOLD/TREND/ISOLATION_FOREST/DATA_LINK",
    )
    level: Mapped[str] = mapped_column(
        String(20), default="WARNING", comment="级别: INFO/WARNING/CRITICAL"
    )
    title: Mapped[str] = mapped_column(String(200), comment="标题")
    description: Mapped[str | None] = mapped_column(Text, comment="描述/证据")
    metric_value: Mapped[float | None] = mapped_column(Float, comment="触发时指标值")
    threshold: Mapped[float | None] = mapped_column(Float, comment="触发的阈值")
    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        index=True,
        comment="状态: PENDING/HANDLED/IGNORED/CONVERTED",
    )
    source: Mapped[str] = mapped_column(String(20), default="AUTO", comment="来源: AUTO/MANUAL")
    handled_by: Mapped[str | None] = mapped_column(String(50), comment="处理人")
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, comment="处理时间")
    handle_note: Mapped[str | None] = mapped_column(Text, comment="处理说明")
