"""融合诊断服务：取设备三路信号 → 诊断 → 落库/查询"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import fusion_engine
from app.models.device import Device, DevicePoint
from app.models.fusion import FusionDiagnosis
from app.models.monitor import SensorData

HISTORY_LIMIT = 30  # 每个点位取最近 30 条用于诊断


def _point_values(db: Session, point_id: int, limit: int = HISTORY_LIMIT) -> list[float]:
    """点位最近值（时间升序）"""
    rows = db.scalars(
        select(SensorData.value)
        .where(SensorData.device_point_id == point_id)
        .order_by(SensorData.collected_at.desc())
        .limit(limit)
    ).all()
    return list(reversed(rows))


def diagnose_device(db: Session, device_id: int) -> dict:
    """对单台设备做融合诊断并写入记录"""
    points = db.scalars(
        select(DevicePoint).where(DevicePoint.device_id == device_id)
    ).all()
    by_type: dict[str, tuple[list[float], float | None]] = {}
    for point in points:
        by_type[point.point_type] = (_point_values(db, point.id), point.alarm_high)

    def values(ptype: str) -> list[float]:
        return by_type.get(ptype, ([], None))[0]

    def high(ptype: str) -> float | None:
        return by_type.get(ptype, ([], None))[1]

    result = fusion_engine.diagnose(
        vibration_values=values("VIBRATION"),
        temperature_values=values("TEMPERATURE"),
        current_values=values("CURRENT"),
        vibration_high=high("VIBRATION"),
        temperature_high=high("TEMPERATURE"),
        current_high=high("CURRENT"),
    )

    record = FusionDiagnosis(
        device_id=device_id,
        fault_type=result.fault_type,
        confidence=result.confidence,
        signals_json={
            "signals": [
                {
                    "name": s.name,
                    "value": s.value,
                    "threshold": s.threshold,
                    "severity": s.severity,
                    "evidence": s.evidence,
                }
                for s in result.signals
            ],
            "recommendation": result.recommendation,
        },
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_dict(record)


def diagnose_all(db: Session) -> dict:
    """对全部在运行设备批量诊断"""
    devices = db.scalars(
        select(Device).where(Device.status == "RUNNING").order_by(Device.id)
    ).all()
    results = [diagnose_device(db, device.id) for device in devices]
    return {"devices": len(devices), "records": len(results)}


def latest_diagnoses(db: Session, device_id: int | None = None, limit: int = 50) -> list[dict]:
    """最近诊断记录（按时间倒序）"""
    stmt = select(FusionDiagnosis).order_by(FusionDiagnosis.created_at.desc()).limit(limit)
    if device_id is not None:
        stmt = stmt.where(FusionDiagnosis.device_id == device_id)
    rows = db.scalars(stmt).all()
    return [_to_dict(row) for row in rows]


def _to_dict(record: FusionDiagnosis) -> dict:
    return {
        "id": record.id,
        "device_id": record.device_id,
        "fault_type": record.fault_type,
        "confidence": record.confidence,
        "signals": (record.signals_json or {}).get("signals", []),
        "recommendation": (record.signals_json or {}).get("recommendation", ""),
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
