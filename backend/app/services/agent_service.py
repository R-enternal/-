"""Agent 业务服务：维保建议生成、计划落库、转工单、派单建议"""

from datetime import date, time
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent import MaintenanceBusyWindow, MaintenancePlan
from app.models.device import Device
from app.models.monitor import Alert, HealthRecord
from app.models.user import SysUser
from app.models.work_order import WorkOrder
from app.services import work_order_service


def _latest_health(db: Session) -> dict[int, tuple[float, str]]:
    """每台设备最新健康度 {device_id: (score, level)}"""
    latest = (
        select(HealthRecord.device_id, func.max(HealthRecord.computed_at).label("latest_at"))
        .group_by(HealthRecord.device_id)
        .subquery()
    )
    rows = db.execute(
        select(HealthRecord.device_id, HealthRecord.score, HealthRecord.level).join(
            latest,
            (HealthRecord.device_id == latest.c.device_id)
            & (HealthRecord.computed_at == latest.c.latest_at),
        )
    ).all()
    return {device_id: (score, level) for device_id, score, level in rows}


def _pending_alerts(db: Session) -> dict[int, list[Alert]]:
    """PENDING 告警按设备分组"""
    alerts = db.scalars(select(Alert).where(Alert.status == "PENDING")).all()
    grouped: dict[int, list[Alert]] = {}
    for alert in alerts:
        grouped.setdefault(alert.device_id, []).append(alert)
    return grouped


def _best_window(db: Session, warehouse_id: int, plan_date: date) -> tuple[time | None, time | None]:
    """取仓库在该日期星期几最闲的时段（busy_level 最小）"""
    row = db.scalar(
        select(MaintenanceBusyWindow)
        .where(
            MaintenanceBusyWindow.warehouse_id == warehouse_id,
            MaintenanceBusyWindow.weekday == plan_date.weekday(),
        )
        .order_by(MaintenanceBusyWindow.busy_level, MaintenanceBusyWindow.start_time)
        .limit(1)
    )
    if row is None:
        return None, None
    return row.start_time, row.end_time


def build_maintenance_suggestions(db: Session, plan_date: date | None = None) -> list[dict]:
    """对每台设备生成维保建议（健康度 + 告警 + 忙闲错峰）"""
    plan_date = plan_date or date.today()
    devices = db.scalars(select(Device).where(Device.status != "SCRAPPED").order_by(Device.id)).all()
    health = _latest_health(db)
    alerts_by_device = _pending_alerts(db)

    suggestions: list[dict] = []
    for device in devices:
        score, level = health.get(device.id, (100.0, "HEALTHY"))
        alerts = alerts_by_device.get(device.id, [])
        critical = any(a.level == "CRITICAL" for a in alerts)
        has_alert = bool(alerts)

        if score < 70 or critical:
            task_type = "REPAIR"
            priority = "URGENT" if critical else "HIGH"
            title = f"{device.name} 检修计划（健康度 {score:.1f}）"
            reason = f"健康度偏低({level}/{score:.1f})，待处理告警 {len(alerts)} 条"
        elif score < 90 or has_alert:
            task_type = "MAINTAIN"
            priority = "HIGH" if has_alert else "MEDIUM"
            title = f"{device.name} 保养计划（健康度 {score:.1f}）"
            reason = f"健康度中等({level}/{score:.1f})，待处理告警 {len(alerts)} 条"
        else:
            task_type = "INSPECT"
            priority = "LOW"
            title = f"{device.name} 例行巡检（健康度 {score:.1f}）"
            reason = f"健康度良好({level}/{score:.1f})，建议例行巡检"

        start, end = _best_window(db, device.warehouse_id, plan_date)
        suggestions.append(
            {
                "device_id": device.id,
                "device_name": device.name,
                "device_code": device.device_code,
                "warehouse_id": device.warehouse_id,
                "score": round(score, 1),
                "level": level,
                "pending_alerts": len(alerts),
                "task_type": task_type,
                "priority": priority,
                "title": title,
                "reason": reason,
                "suggested_start": start.strftime("%H:%M") if start else None,
                "suggested_end": end.strftime("%H:%M") if end else None,
            }
        )
    # 按紧急程度排序：REPAIR > MAINTAIN > INSPECT
    order = {"REPAIR": 0, "MAINTAIN": 1, "INSPECT": 2}
    suggestions.sort(key=lambda s: (order.get(s["task_type"], 9), -s["score"]))
    return suggestions


def create_plans_from_suggestions(
    db: Session, plan_date: date | None = None, created_by: str | None = "agent"
) -> list[MaintenancePlan]:
    """把维保建议批量落库（DRAFT）"""
    plan_date = plan_date or date.today()
    suggestions = build_maintenance_suggestions(db, plan_date)
    plans: list[MaintenancePlan] = []
    for sug in suggestions:
        start = time.fromisoformat(sug["suggested_start"]) if sug["suggested_start"] else None
        end = time.fromisoformat(sug["suggested_end"]) if sug["suggested_end"] else None
        plan = MaintenancePlan(
            warehouse_id=sug["warehouse_id"],
            device_id=sug["device_id"],
            plan_date=plan_date,
            start_time=start,
            end_time=end,
            task_type=sug["task_type"],
            title=sug["title"],
            reason=sug["reason"],
            status="DRAFT",
            source="AGENT",
            created_by=created_by,
        )
        db.add(plan)
        plans.append(plan)
    db.commit()
    for plan in plans:
        db.refresh(plan)
    return plans


def list_plans(db: Session, status: str | None = None) -> list[dict]:
    """维保计划列表（带设备/仓库名称）"""
    stmt = (
        select(MaintenancePlan, Device.name, Device.device_code)
        .join(Device, Device.id == MaintenancePlan.device_id)
        .order_by(MaintenancePlan.plan_date.desc(), MaintenancePlan.id.desc())
    )
    if status:
        stmt = stmt.where(MaintenancePlan.status == status)
    rows = db.execute(stmt).all()
    return [
        {
            "id": plan.id,
            "device_id": plan.device_id,
            "device_name": device_name,
            "device_code": device_code,
            "plan_date": plan.plan_date.isoformat(),
            "start_time": plan.start_time.strftime("%H:%M") if plan.start_time else None,
            "end_time": plan.end_time.strftime("%H:%M") if plan.end_time else None,
            "task_type": plan.task_type,
            "title": plan.title,
            "reason": plan.reason,
            "status": plan.status,
            "source": plan.source,
            "work_order_id": plan.work_order_id,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
        }
        for plan, device_name, device_code in rows
    ]


def plan_to_work_order(db: Session, plan_id: int) -> dict:
    """维保计划转工单：创建工单并更新计划状态（同一事务）"""
    plan = db.get(MaintenancePlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"维保计划不存在: {plan_id}")
    if plan.status != "DRAFT":
        raise HTTPException(status_code=400, detail=f"当前状态 {plan.status} 不允许转工单（仅 DRAFT 可转）")
    if plan.work_order_id is not None:
        raise HTTPException(status_code=400, detail="该计划已转工单")

    priority_map = {"REPAIR": "HIGH", "MAINTAIN": "MEDIUM", "INSPECT": "LOW"}
    order = work_order_service.create_work_order(
        db,
        work_order_service.WorkOrderCreate(
            warehouse_id=plan.warehouse_id,
            device_id=plan.device_id,
            title=plan.title,
            description=f"【AI 维保计划】{plan.reason or ''}",
            order_type=plan.task_type,
            priority=priority_map.get(plan.task_type, "MEDIUM"),
            source="PLAN",
        ),
    )
    plan.work_order_id = order.id
    plan.status = "CONFIRMED"
    db.commit()
    return work_order_service.work_order_with_names(db, order)


def assign_suggestions(db: Session) -> list[dict]:
    """待派单工单的智能调度建议：按优先级 + 设备健康度排序，附建议指派人"""
    orders = db.scalars(
        select(WorkOrder).where(WorkOrder.status == "PENDING_ASSIGN").order_by(WorkOrder.created_at)
    ).all()
    if not orders:
        return []
    health = _latest_health(db)
    workers = db.scalars(
        select(SysUser).where(SysUser.role == "MAINTENANCE_WORKER", SysUser.status == "ACTIVE")
    ).all()

    priority_rank = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    suggestions: list[dict[str, Any]] = []
    for order in orders:
        score = health.get(order.device_id, (100.0, "HEALTHY"))[0]
        device = db.get(Device, order.device_id)
        suggestions.append(
            {
                "order_id": order.id,
                "order_no": order.order_no,
                "title": order.title,
                "device_name": device.name if device else None,
                "priority": order.priority,
                "device_score": round(score, 1),
                "suggested_assignee_id": workers[0].id if workers else None,
                "suggested_assignee_name": workers[0].real_name if workers else None,
                "reason": f"优先级{order.priority}，设备健康度 {score:.1f}",
            }
        )
    suggestions.sort(key=lambda s: (priority_rank.get(s["priority"], 9), s["device_score"]))
    return suggestions
