"""工单路由"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ok
from app.schemas.work_order import (
    WorkOrderCreate,
    WorkOrderPartAdd,
    WorkOrderTransition,
)
from app.services import work_order_service

router = APIRouter(prefix="/api/work-orders", tags=["工单"])


@router.post("")
def create_work_order(data: WorkOrderCreate, db: Session = Depends(get_db)) -> dict:
    """创建工单（初始状态 PENDING_ASSIGN）"""
    order = work_order_service.create_work_order(db, data)
    return ok(
        data=work_order_service.work_order_with_names(db, order),
        message=f"工单创建成功：{order.order_no}",
    )


@router.get("")
def list_work_orders(
    status: str | None = None,
    device_id: int | None = None,
    assignee_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """工单列表（支持按状态/设备/指派人过滤）"""
    items = work_order_service.list_work_orders_with_context(
        db, status=status, device_id=device_id, assignee_id=assignee_id
    )
    return ok(data=items)


@router.get("/{order_id}")
def get_work_order(order_id: int, db: Session = Depends(get_db)) -> dict:
    """工单详情"""
    order = work_order_service.get_work_order(db, order_id)
    data = work_order_service.work_order_with_names(db, order)
    data["parts"] = work_order_service.list_order_parts(db, order_id)
    return ok(data=data)


@router.post("/{order_id}/transition")
def transition_work_order(
    order_id: int, data: WorkOrderTransition, db: Session = Depends(get_db)
) -> dict:
    """状态流转（非法跳转返回 400）"""
    order = work_order_service.transition_work_order(db, order_id, data)
    return ok(
        data=work_order_service.work_order_with_names(db, order),
        message=f"工单已流转至 {order.status}",
    )


@router.post("/{order_id}/parts")
def add_order_part(order_id: int, data: WorkOrderPartAdd, db: Session = Depends(get_db)) -> dict:
    """登记工单使用备件（同备件重复登记累加数量）"""
    wop = work_order_service.add_part_to_order(db, order_id, data)
    return ok(
        data={
            "id": wop.id,
            "work_order_id": wop.work_order_id,
            "spare_part_id": wop.spare_part_id,
            "quantity": wop.quantity,
        },
        message="备件登记成功",
    )


@router.get("/{order_id}/parts")
def list_order_parts(order_id: int, db: Session = Depends(get_db)) -> dict:
    """工单备件明细列表"""
    return ok(data=work_order_service.list_order_parts(db, order_id))
