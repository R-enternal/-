"""融合诊断模型：多传感器联合诊断结果记录"""

from sqlalchemy import JSON, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import IdMixin, TenantMixin, TimestampMixin


class FusionDiagnosis(IdMixin, TenantMixin, TimestampMixin, Base):
    """设备融合诊断记录（振动+温度+电流联合判定故障模式）"""

    __tablename__ = "fusion_diagnosis"

    device_id: Mapped[int] = mapped_column(
        ForeignKey("device.id"), index=True, comment="诊断对象设备"
    )
    fault_type: Mapped[str] = mapped_column(
        String(30),
        index=True,
        comment="故障模式: NORMAL/BEARING_WEAR/MOTOR_OVERHEAT/LOAD_ABNORMAL/COMPOSITE_FAULT",
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0, comment="置信度 0-1")
    signals_json: Mapped[dict | None] = mapped_column(JSON, comment="各信号证据（值/趋势/严重度）")
