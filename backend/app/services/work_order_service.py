"""工单服务：创建、状态流转、查询

状态机（可解释）：
    PENDING_ASSIGN → PENDING_EXECUTE → IN_PROGRESS → PENDING_ACCEPT → COMPLETED
    任意状态 → CANCELLED
非法流转（如创建后直接验收）返回 400。
"""

import random
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.monitor import Alert
from app.models.spare_part import SparePart, StockRecord
from app.models.user import SysUser
from app.models.warehouse import Warehouse
from app.models.work_order import WorkOrder, WorkOrderPart
from app.schemas.work_order import (
    WorkOrderCreate,
    WorkOrderPartAdd,
    WorkOrderTransition,
)
from app.services import notification_service

# 合法状态流转表：当前状态 → 允许的目标状态集合
TRANSITIONS: dict[str, set[str]] = {
    "PENDING_ASSIGN": {"PENDING_EXECUTE", "CANCELLED"},
    "PENDING_EXECUTE": {"IN_PROGRESS", "CANCELLED"},
    "IN_PROGRESS": {"PENDING_ACCEPT", "CANCELLED"},
    "PENDING_ACCEPT": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}

# 流转动作 → 目标状态
ACTIONS: dict[str, str] = {
    "assign": "PENDING_EXECUTE",  # 派单
    "start": "IN_PROGRESS",  # 开始执行
    "submit": "PENDING_ACCEPT",  # 提交验收
    "complete": "COMPLETED",  # 验收通过
    "cancel": "CANCELLED",  # 取消
}


def generate_order_no() -> str:
    """生成工单编号：WO + 时间戳 + 4 位随机数"""
    return f"WO{datetime.now():%Y%m%d%H%M%S}{random.randint(1000, 9999)}"


def create_work_order(db: Session, data: WorkOrderCreate) -> WorkOrder:
    """创建工单（初始状态 PENDING_ASSIGN）"""
    # 校验仓库/设备存在
    if db.get(Warehouse, data.warehouse_id) is None:
        raise HTTPException(status_code=404, detail=f"仓库不存在: {data.warehouse_id}")
    if db.get(Device, data.device_id) is None:
        raise HTTPException(status_code=404, detail=f"设备不存在: {data.device_id}")

    order = WorkOrder(
        order_no=generate_order_no(),
        warehouse_id=data.warehouse_id,
        device_id=data.device_id,
        title=data.title,
        description=data.description,
        order_type=data.order_type,
        priority=data.priority,
        source=data.source,
        status="PENDING_ASSIGN",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def create_from_alert(db: Session, alert_id: int) -> WorkOrder:
    """告警转工单：仅 HANDLED 状态可转，转后告警变 CONVERTED（防重复转）

    标题/描述从告警带出，仓库从告警关联的设备取。
    工单创建与告警状态变更在同一事务提交。
    """
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"告警不存在: {alert_id}")
    if alert.status != "HANDLED":
        raise HTTPException(
            status_code=400,
            detail=f"当前状态 {alert.status} 不允许转工单（需先确认 HANDLED）",
        )

    device = db.get(Device, alert.device_id)
    if device is None:
        raise HTTPException(status_code=404, detail=f"告警关联的设备不存在: {alert.device_id}")

    handle_note = f"（处理备注：{alert.handle_note}）" if alert.handle_note else ""
    order = WorkOrder(
        order_no=generate_order_no(),
        warehouse_id=device.warehouse_id,
        device_id=alert.device_id,
        title=alert.title,
        description=f"{alert.description or ''}{handle_note}",
        source="ALERT",
        alert_id=alert.id,
        status="PENDING_ASSIGN",
    )
    db.add(order)
    alert.status = "CONVERTED"
    db.commit()
    db.refresh(order)
    return order


def transition_work_order(db: Session, order_id: int, data: WorkOrderTransition) -> WorkOrder:
    """状态流转：校验前置状态，非法流转返回 400"""
    order = get_work_order(db, order_id)
    target = ACTIONS.get(data.action)
    if target is None:
        raise HTTPException(status_code=400, detail=f"未知流转动作: {data.action}")

    if target not in TRANSITIONS[order.status]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"非法流转：{order.status} 不能通过 {data.action} "
                f"变为 {target}（允许: {sorted(TRANSITIONS[order.status])}）"
            ),
        )

    # 动作附带信息与副作用（全部在同一事务，由 db.commit 统一提交）
    if data.action == "assign":
        # 派单必须指定指派人，且用户必须存在（第 15 步演示账号落地后启用）
        if data.assignee_id is None:
            raise HTTPException(status_code=400, detail="派单必须指定指派人 assignee_id")
        if db.get(SysUser, data.assignee_id) is None:
            raise HTTPException(status_code=404, detail=f"指派人不存在: {data.assignee_id}")
        order.assignee_id = data.assignee_id
        # 通知：派单 → 发给所有 ADMIN + 指派人
        notification_service.notify(
            db,
            notify_type="WORK_ORDER",
            title=f"工单已派单：{order.title}",
            content=f"工单号 {order.order_no}，等待执行",
            ref_type="WORK_ORDER",
            ref_id=order.id,
            extra_user_ids=[data.assignee_id],
        )
    if data.action == "start":
        order.actual_start = datetime.now()
    if data.action == "complete":
        _apply_parts_for_completion(db, order)  # 校验库存 + 扣减 + 写流水
        order.actual_end = datetime.now()
        order.result = data.result
    if data.action == "cancel":
        _rollback_parts_on_cancel(db, order)  # 取消时清明细（尚未扣库存）

    order.status = target
    db.commit()
    db.refresh(order)
    return order


def add_part_to_order(db: Session, order_id: int, data: WorkOrderPartAdd) -> WorkOrderPart:
    """登记工单使用备件（仅执行/待验收阶段可登记，同备件重复登记累加数量）"""
    order = get_work_order(db, order_id)
    if order.status not in {"PENDING_EXECUTE", "IN_PROGRESS", "PENDING_ACCEPT"}:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态 {order.status} 不允许登记备件",
        )
    part = db.get(SparePart, data.spare_part_id)
    if part is None:
        raise HTTPException(status_code=404, detail=f"备件不存在: {data.spare_part_id}")

    existing = db.scalar(
        select(WorkOrderPart)
        .where(
            WorkOrderPart.work_order_id == order_id,
            WorkOrderPart.spare_part_id == data.spare_part_id,
        )
        .limit(1)
    )
    if existing is not None:
        existing.quantity += data.quantity
        wop = existing
    else:
        wop = WorkOrderPart(
            work_order_id=order_id,
            spare_part_id=data.spare_part_id,
            quantity=data.quantity,
            unit_price=part.price,
        )
        db.add(wop)
    db.commit()
    db.refresh(wop)
    return wop


def list_order_parts(db: Session, order_id: int) -> list[dict]:
    """工单备件明细（带备件名称/编号）"""
    get_work_order(db, order_id)
    rows = db.execute(
        select(WorkOrderPart, SparePart.name, SparePart.part_code)
        .join(SparePart, SparePart.id == WorkOrderPart.spare_part_id)
        .where(WorkOrderPart.work_order_id == order_id)
    ).all()
    return [
        {
            "id": wop.id,
            "spare_part_id": wop.spare_part_id,
            "part_code": code,
            "part_name": name,
            "quantity": wop.quantity,
            "unit_price": wop.unit_price,
            "created_at": wop.created_at,
        }
        for wop, name, code in rows
    ]


def _apply_parts_for_completion(db: Session, order: WorkOrder) -> None:
    """工单完成时扣减备件库存 + 写 WORK_ORDER 流水（与状态流转同一事务）

    先全部校验库存，再统一扣减，避免"扣了一半发现另一个不够"。
    """
    items = db.scalars(select(WorkOrderPart).where(WorkOrderPart.work_order_id == order.id)).all()
    if not items:
        return

    # 1. 校验全部明细库存充足（同时收集备件引用，供统一扣减）
    resolved: list[tuple[WorkOrderPart, SparePart]] = []
    for wop in items:
        part = db.get(SparePart, wop.spare_part_id)
        if part is None:
            raise HTTPException(status_code=400, detail=f"备件不存在: {wop.spare_part_id}")
        if part.stock_quantity < wop.quantity:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"备件 {part.name} 库存不足："
                    f"需要 {wop.quantity}，当前 {part.stock_quantity}"
                ),
            )
        resolved.append((wop, part))

    # 2. 统一扣减 + 写流水
    for wop, part in resolved:
        part.stock_quantity -= wop.quantity
        db.add(
            StockRecord(
                spare_part_id=part.id,
                change_type="WORK_ORDER",
                quantity=-wop.quantity,
                balance_after=part.stock_quantity,
                related_work_order_id=order.id,
                remark=f"工单 {order.order_no} 消耗",
            )
        )


def _rollback_parts_on_cancel(db: Session, order: WorkOrder) -> None:
    """工单取消时删除未消耗的备件明细（取消前未扣库存，只需清明细）"""
    db.execute(delete(WorkOrderPart).where(WorkOrderPart.work_order_id == order.id))


def get_work_order(db: Session, order_id: int) -> WorkOrder:
    """工单详情（404 兜底）"""
    order = db.get(WorkOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"工单不存在: {order_id}")
    return order


def list_work_orders(
    db: Session,
    status: str | None = None,
    device_id: int | None = None,
    assignee_id: int | None = None,
) -> list[WorkOrder]:
    """工单列表（按创建时间倒序，支持过滤）"""
    stmt = select(WorkOrder).order_by(WorkOrder.created_at.desc())
    if status:
        stmt = stmt.where(WorkOrder.status == status)
    if device_id is not None:
        stmt = stmt.where(WorkOrder.device_id == device_id)
    if assignee_id is not None:
        stmt = stmt.where(WorkOrder.assignee_id == assignee_id)
    return list(db.scalars(stmt))


def _base_order_dict(order: WorkOrder) -> dict:
    """工单基础字段（不含关联名称，供详情/列表复用）"""
    return {
        "id": order.id,
        "order_no": order.order_no,
        "warehouse_id": order.warehouse_id,
        "device_id": order.device_id,
        "title": order.title,
        "description": order.description,
        "order_type": order.order_type,
        "priority": order.priority,
        "source": order.source,
        "alert_id": order.alert_id,
        "assignee_id": order.assignee_id,
        "status": order.status,
        "scheduled_start": order.scheduled_start,
        "scheduled_end": order.scheduled_end,
        "actual_start": order.actual_start,
        "actual_end": order.actual_end,
        "result": order.result,
        "created_at": order.created_at,
    }


def work_order_with_names(db: Session, order: WorkOrder) -> dict:
    """工单详情响应（附带仓库/设备/来源告警信息，单条查询）"""
    data = _base_order_dict(order)
    wh = db.get(Warehouse, order.warehouse_id)
    device = db.get(Device, order.device_id)
    alert = db.get(Alert, order.alert_id) if order.alert_id else None
    data["warehouse_name"] = wh.name if wh else None
    data["device_name"] = device.name if device else None
    data["alert_info"] = (
        {
            "id": alert.id,
            "title": alert.title,
            "alert_type": alert.alert_type,
            "level": alert.level,
        }
        if alert is not None
        else None
    )
    return data


def list_work_orders_with_context(
    db: Session,
    status: str | None = None,
    device_id: int | None = None,
    assignee_id: int | None = None,
) -> list[dict]:
    """工单列表（一次 join 带出仓库/设备/告警上下文，避免 N+1）"""
    stmt = (
        select(
            WorkOrder,
            Warehouse.name,
            Device.name,
            Alert.id,
            Alert.title,
            Alert.alert_type,
            Alert.level,
        )
        .join(Warehouse, Warehouse.id == WorkOrder.warehouse_id)
        .join(Device, Device.id == WorkOrder.device_id)
        .outerjoin(Alert, Alert.id == WorkOrder.alert_id)
        .order_by(WorkOrder.created_at.desc())
    )
    if status:
        stmt = stmt.where(WorkOrder.status == status)
    if device_id is not None:
        stmt = stmt.where(WorkOrder.device_id == device_id)
    if assignee_id is not None:
        stmt = stmt.where(WorkOrder.assignee_id == assignee_id)

    rows = db.execute(stmt).all()
    result: list[dict] = []
    for row in rows:
        order, wh_name, device_name, alert_id, alert_title, alert_type, alert_level = row
        data = _base_order_dict(order)
        data["warehouse_name"] = wh_name
        data["device_name"] = device_name
        data["alert_info"] = (
            {
                "id": alert_id,
                "title": alert_title,
                "alert_type": alert_type,
                "level": alert_level,
            }
            if alert_id is not None
            else None
        )
        result.append(data)
    return result
