"""告警服务：阈值判定 → 去重 → 写入 alert 表"""

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Row, select
from sqlalchemy.orm import Session

from app.config import config
from app.core.predictive_engine import PredictiveResult, check_predictive
from app.core.threshold_engine import ThresholdResult, check_threshold
from app.core.trend_engine import TrendResult, check_trend
from app.models.device import Device, DevicePoint
from app.models.monitor import Alert, SensorData
from app.services import notification_service
from app.services.sensor_service import list_active_points


def check_all_points(db: Session) -> dict:
    """对所有启用点位执行阈值 + 趋势双判定，生成（或跳过）告警

    流程（可解释）：
    1. 取每个点位足够长的数据序列
    2. 阈值引擎判定（连续 N 次超限）
    3. 趋势引擎判定（滑动窗口持续上升）
    4. 去重：同点位同类型已有 PENDING 告警则跳过
    5. 生成告警，记录完整证据（设备/点位/阈值/实际值/触发层）
    """
    points = list_active_points(db)
    created = 0

    for point in points:
        # 1. 取足够长的数据序列（覆盖阈值防抖窗口和趋势窗口的较大值）
        max_needed = max(config.alert_debounce_count, point.trend_window)
        recent = db.scalars(
            select(SensorData.value)
            .where(SensorData.device_point_id == point.id)
            .order_by(SensorData.collected_at.desc())
            .limit(max_needed)
        ).all()
        values = list(reversed(recent))

        # 2. 阈值判定（连续 N 次超限）
        result = check_threshold(
            alarm_low=point.alarm_low,
            alarm_high=point.alarm_high,
            recent_values=values,
            debounce_count=config.alert_debounce_count,
        )
        if result is not None and _create_alert_if_new(db, point, result, "THRESHOLD"):
            created += 1

        # 3. 趋势判定（滑动窗口持续上升）
        trend_result = check_trend(
            recent_values=values,
            trend_delta=point.trend_delta,
            trend_window=point.trend_window,
        )
        if trend_result is not None and _create_alert_if_new(db, point, trend_result, "TREND"):
            created += 1

        # 4. 预测判定（Holt 双指数平滑，提前预警超限）
        predictive_result = check_predictive(
            alarm_low=point.alarm_low,
            alarm_high=point.alarm_high,
            recent_values=values,
            horizon=config.predictive_horizon,
            window=config.predictive_window,
        )
        if predictive_result is not None and _create_alert_if_new(
            db, point, predictive_result, "PREDICTIVE"
        ):
            created += 1

    db.commit()
    return {"points": len(points), "created": created}


def _create_alert_if_new(
    db: Session,
    point: DevicePoint,
    result: ThresholdResult | TrendResult | PredictiveResult,
    trigger_layer: str,
) -> bool:
    """去重 + 生成告警。返回是否新增（True=新增，False=已存在跳过）"""
    # 去重：同点位同类型存在未处理告警则不重复生成
    pending = db.scalar(
        select(Alert.id)
        .where(
            Alert.point_id == point.id,
            Alert.alert_type == result.alert_type,
            Alert.status == "PENDING",
        )
        .limit(1)
    )
    if pending is not None:
        return False

    # 按触发层生成可解释的描述（用 isinstance 做类型收窄）
    if isinstance(result, PredictiveResult):
        title = f"{point.point_type} 预测超限预警"
        description = (
            f"当前值 {result.metric_value}，按当前趋势预计 {result.eta_steps} 个采样周期后"
            f"达到阈值 {result.threshold}（预测值 {result.predicted_value}，趋势斜率 {result.trend}）"
        )
    elif isinstance(result, TrendResult):
        title = f"{point.point_type} 持续上升预警"
        description = (
            f"滑动窗口内持续上升 {result.rise_amount}，"
            f"当前值 {result.metric_value}，阈值 {result.threshold}，斜率 {result.slope}"
        )
    else:
        title = f"{point.point_type} 超限告警"
        description = (
            f"连续 {config.alert_debounce_count} 次采样超限，"
            f"最近值 {result.metric_value}，阈值 {result.threshold}"
        )

    alert = Alert(
        device_id=point.device_id,
        point_id=point.id,
        alert_type=result.alert_type,
        trigger_layer=trigger_layer,
        level=result.level,
        title=title,
        description=description,
        metric_value=result.metric_value,
        threshold=result.threshold,
        status="PENDING",
        source="AUTO",
    )
    db.add(alert)
    db.flush()  # 拿到 alert.id 作为通知关联
    # 通知：告警生成 → 发给所有 ADMIN
    notification_service.notify(
        db,
        notify_type="ALERT",
        title=f"新告警：{point.point_type} {result.alert_type}",
        content=description,
        ref_type="ALERT",
        ref_id=alert.id,
    )
    return True


def list_alerts_with_context(
    db: Session,
    device_id: int | None = None,
    status: str | None = None,
) -> list[dict]:
    """告警列表（一次 join 查询带出设备/点位上下文，避免 N+1）"""
    stmt = (
        select(Alert, Device.name, DevicePoint.point_code, DevicePoint.point_type)
        .join(Device, Device.id == Alert.device_id)
        .outerjoin(DevicePoint, DevicePoint.id == Alert.point_id)  # outer：point_id 可空
        .order_by(Alert.created_at.desc())
    )
    if device_id is not None:
        stmt = stmt.where(Alert.device_id == device_id)
    if status:
        stmt = stmt.where(Alert.status == status)
    rows = db.execute(stmt).all()
    return [_row_to_alert_dict(row) for row in rows]


def get_alert_with_context(db: Session, alert_id: int) -> dict | None:
    """告警详情（附带设备名/点位信息，供前端展示）"""
    row = db.execute(
        select(Alert, Device.name, DevicePoint.point_code, DevicePoint.point_type)
        .join(Device, Device.id == Alert.device_id)
        .outerjoin(DevicePoint, DevicePoint.id == Alert.point_id)
        .where(Alert.id == alert_id)
    ).first()
    if row is None:
        return None
    return _row_to_alert_dict(row)


def _row_to_alert_dict(row: Row[Any]) -> dict:
    """把 (Alert, device_name, point_code, point_type) 行转换为响应 dict"""
    alert, device_name, point_code, point_type = row
    return {
        "id": alert.id,
        "device_name": device_name,
        "point_code": point_code,
        "point_type": point_type,
        "alert_type": alert.alert_type,
        "trigger_layer": alert.trigger_layer,
        "level": alert.level,
        "title": alert.title,
        "description": alert.description,
        "metric_value": alert.metric_value,
        "threshold": alert.threshold,
        "status": alert.status,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


def handle_alert(
    db: Session,
    alert_id: int,
    handled_by: str | None = None,
    handle_note: str | None = None,
) -> Alert:
    """确认告警：PENDING → HANDLED，记录处理人/时间/说明"""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"告警不存在: {alert_id}")
    if alert.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"当前状态 {alert.status} 不允许确认（仅 PENDING 可处理）",
        )
    alert.status = "HANDLED"
    alert.handled_by = handled_by
    alert.handled_at = datetime.now()
    alert.handle_note = handle_note
    db.commit()
    db.refresh(alert)
    return alert


def ignore_alert(
    db: Session,
    alert_id: int,
    handled_by: str | None = None,
    handle_note: str | None = None,
) -> Alert:
    """忽略告警：PENDING → IGNORED，同样记录处理信息"""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"告警不存在: {alert_id}")
    if alert.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"当前状态 {alert.status} 不允许忽略（仅 PENDING 可处理）",
        )
    alert.status = "IGNORED"
    alert.handled_by = handled_by
    alert.handled_at = datetime.now()
    alert.handle_note = handle_note
    db.commit()
    db.refresh(alert)
    return alert
