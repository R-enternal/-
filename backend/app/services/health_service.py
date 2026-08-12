"""健康度服务：点位打分 → 设备聚合 → 写入 health_record"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.anomaly_engine import IsolationForestEngine
from app.core.health_score import (
    POINT_TYPE_WEIGHTS,
    PointScore,
    aggregate_device,
    level_of,
    score_point,
)
from app.models.device import DevicePoint
from app.models.monitor import Alert, HealthRecord, SensorData

CV_WINDOW = 30  # 稳定性窗口（最近 N 条）
HISTORY_LIMIT = 300  # 孤立森林训练用历史上限

# 孤立森林模型缓存（point_id -> engine），数据量变化时自动重训
_anomaly_models: dict[int, IsolationForestEngine] = {}


def _get_anomaly_engine(point_id: int) -> IsolationForestEngine:
    """获取（或创建）某点位的孤立森林引擎"""
    engine = _anomaly_models.get(point_id)
    if engine is None:
        engine = IsolationForestEngine(seed=42)
        _anomaly_models[point_id] = engine
    return engine


def compute_all_health(db: Session) -> dict:
    """对每台有启用点位的设备计算健康度并写入 health_record

    流程：
    1. 取所有启用点位（按设备分组）
    2. 取每个点位最近数据 + PENDING 告警
    3. 点位打分（告警/稳定性/孤立森林）
    4. 加权聚合 → 等级 → 写记录（factor_json 存证据）
    """
    points = db.scalars(select(DevicePoint).where(DevicePoint.enabled.is_(True))).all()
    if not points:
        return {"devices": 0, "records": 0}

    # 一次查出所有 PENDING 告警，按 point_id 分组（避免 N+1 查询）
    alerts = db.scalars(select(Alert).where(Alert.status == "PENDING")).all()
    alerts_by_point: dict[int, list[Alert]] = {}
    for a in alerts:
        if a.point_id is not None:
            alerts_by_point.setdefault(a.point_id, []).append(a)

    # 按设备分组点位
    points_by_device: dict[int, list[DevicePoint]] = {}
    for p in points:
        points_by_device.setdefault(p.device_id, []).append(p)

    records = 0
    for device_id, device_points in points_by_device.items():
        point_scores: list[PointScore] = []

        for point in device_points:
            # 取最近 HISTORY_LIMIT 条数据（时间升序）
            recent = db.scalars(
                select(SensorData.value)
                .where(SensorData.device_point_id == point.id)
                .order_by(SensorData.collected_at.desc())
                .limit(HISTORY_LIMIT)
            ).all()
            values = list(reversed(recent))
            if not values:
                continue

            # 该点位告警情况
            point_alerts = alerts_by_point.get(point.id, [])
            threshold_level = next(
                (a.level for a in point_alerts if a.alert_type.startswith("THRESHOLD")),
                None,
            )
            has_trend = any(a.alert_type == "TREND" for a in point_alerts)
            has_predictive = any(
                a.alert_type in ("PREDICTIVE_HIGH", "PREDICTIVE_LOW") for a in point_alerts
            )

            # 孤立森林异常分（数据足够时自动训练）
            engine = _get_anomaly_engine(point.id)
            engine.fit(values)
            anomaly_score = engine.anomaly_score(values[-1])

            point_scores.append(
                score_point(
                    point_id=point.id,
                    point_type=point.point_type,
                    threshold_alert_level=threshold_level,
                    has_trend_alert=has_trend,
                    has_predictive_alert=has_predictive,
                    recent_values=values[-CV_WINDOW:],
                    anomaly_score=anomaly_score,
                )
            )

        if not point_scores:
            continue

        device_score = aggregate_device(point_scores)
        level = level_of(device_score)
        db.add(
            HealthRecord(
                device_id=device_id,
                score=device_score,
                level=level,
                factor_json={
                    "points": [
                        {
                            "point_id": ps.point_id,
                            "point_type": ps.point_type,
                            "score": ps.score,
                            "deductions": ps.deductions,
                            "anomaly_score": ps.anomaly_score,
                        }
                        for ps in point_scores
                    ],
                    "weights": POINT_TYPE_WEIGHTS,
                },
            )
        )
        records += 1

    db.commit()
    return {"devices": len(points_by_device), "records": records}


def list_health_records(
    db: Session,
    device_id: int | None = None,
    limit: int = 100,
) -> list[dict]:
    """健康度记录列表（按时间倒序，趋势图数据源）"""
    stmt = select(HealthRecord).order_by(HealthRecord.computed_at.desc()).limit(limit)
    if device_id is not None:
        stmt = stmt.where(HealthRecord.device_id == device_id)
    items = db.scalars(stmt).all()
    return [
        {
            "id": r.id,
            "device_id": r.device_id,
            "score": r.score,
            "level": r.level,
            "factor_json": r.factor_json,
            "computed_at": r.computed_at.isoformat() if r.computed_at else None,
        }
        for r in items
    ]
