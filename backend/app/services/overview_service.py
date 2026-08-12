"""看板总览服务：一次请求聚合首页 KPI 数据"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.monitor import Alert, HealthRecord
from app.models.spare_part import SparePart
from app.models.work_order import WorkOrder


def _status_count_map(
    db: Session,
    model: type,
    status_col: str = "status",
) -> dict[str, int]:
    """按状态分组计数（设备/告警/工单通用）"""
    rows = db.execute(
        select(getattr(model, status_col), func.count()).group_by(getattr(model, status_col))
    ).all()
    result: dict[str, int] = {}
    for status, count in rows:
        result[status] = count
    return result


def get_overview_stats(db: Session) -> dict:
    """聚合首页 KPI：设备/健康度/告警/工单/备件

    健康度取每台设备最新一条 health_record 的等级，
    没有记录的设备归入 no_data。
    """
    # ---------- 设备 ----------
    device_total = db.scalar(select(func.count()).select_from(Device)) or 0
    device_by_status = _status_count_map(db, Device)

    # ---------- 健康度（每台设备最新记录） ----------
    latest_subq = (
        select(
            HealthRecord.device_id,
            func.max(HealthRecord.computed_at).label("latest_at"),
        )
        .group_by(HealthRecord.device_id)
        .subquery()
    )
    health_rows = db.execute(
        select(HealthRecord.device_id, HealthRecord.level).join(
            latest_subq,
            (HealthRecord.device_id == latest_subq.c.device_id)
            & (HealthRecord.computed_at == latest_subq.c.latest_at),
        )
    ).all()
    health_count: dict[str, int] = {"HEALTHY": 0, "SUB_HEALTHY": 0, "ABNORMAL": 0}
    for _device_id, level in health_rows:
        if level in health_count:
            health_count[level] += 1
    health_count["NO_DATA"] = device_total - len(health_rows)

    # ---------- 告警 ----------
    alert_by_status = _status_count_map(db, Alert)

    # ---------- 工单 ----------
    order_by_status = _status_count_map(db, WorkOrder)

    # ---------- 备件 ----------
    part_total = db.scalar(select(func.count()).select_from(SparePart)) or 0
    low_stock = db.scalar(
        select(func.count())
        .select_from(SparePart)
        .where(
            SparePart.safe_quantity > 0,
            SparePart.stock_quantity < SparePart.safe_quantity,
        )
    ) or 0

    return {
        "devices": {
            "total": device_total,
            **{
                s: device_by_status.get(s, 0)
                for s in ("RUNNING", "STOPPED", "MAINTENANCE", "SCRAPPED")
            },
        },
        "health": health_count,
        "alerts": {
            "total": sum(alert_by_status.values()),
            "pending": alert_by_status.get("PENDING", 0),
            "handled": alert_by_status.get("HANDLED", 0),
            "ignored": alert_by_status.get("IGNORED", 0),
            "converted": alert_by_status.get("CONVERTED", 0),
        },
        "work_orders": {
            "total": sum(order_by_status.values()),
            "pending_assign": order_by_status.get("PENDING_ASSIGN", 0),
            "in_progress": order_by_status.get("IN_PROGRESS", 0),
            "pending_accept": order_by_status.get("PENDING_ACCEPT", 0),
            "completed": order_by_status.get("COMPLETED", 0),
            "cancelled": order_by_status.get("CANCELLED", 0),
        },
        "spare_parts": {
            "total": part_total,
            "low_stock": low_stock,
        },
    }
