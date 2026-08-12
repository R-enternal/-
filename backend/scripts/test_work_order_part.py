"""工单消耗备件验收测试

验证项：
1. 登记备件（重复登记累加）
2. 工单完成：库存减少 + WORK_ORDER 流水 + 明细三者一致
3. 库存不足时完成被拒绝（400），库存/状态/流水不变
4. 工单取消：明细回滚（删除），库存未扣

运行方式（backend 目录下）：python scripts/test_work_order_part.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.device import Device  # noqa: E402
from app.models.spare_part import SparePart, StockRecord  # noqa: E402
from app.models.user import Notification, SysUser  # noqa: E402
from app.models.warehouse import Warehouse  # noqa: E402
from app.models.work_order import WorkOrder, WorkOrderPart  # noqa: E402
from app.schemas.spare_part import SparePartCreate  # noqa: E402
from app.schemas.work_order import (  # noqa: E402
    WorkOrderCreate,
    WorkOrderPartAdd,
    WorkOrderTransition,
)
from app.services import spare_part_service, work_order_service  # noqa: E402


def _transition(
    db,
    order_id: int,
    action: str,
    result: str | None = None,
    assignee_id: int | None = None,
) -> WorkOrder:
    return work_order_service.transition_work_order(
        db,
        order_id,
        WorkOrderTransition(action=action, result=result, assignee_id=assignee_id),
    )


def test_work_order_part_flow() -> None:
    db = SessionLocal()
    suffix = str(int(datetime.now().timestamp()))

    wh = Warehouse(name=f"工单备件测试仓-{suffix}")
    db.add(wh)
    db.commit()

    device = Device(
        warehouse_id=wh.id,
        device_code=f"WOP-{suffix}",
        name="工单备件测试设备",
        device_type="CONVEYOR",
    )
    db.add(device)
    db.commit()

    user = SysUser(
        username=f"wop_user_{suffix}",
        password_hash=hash_password("pass123"),
        real_name="工单备件测试用户",
        role="MAINTENANCE_WORKER",
    )
    db.add(user)
    db.commit()

    part = spare_part_service.create_spare_part(
        db,
        SparePartCreate(
            warehouse_id=wh.id,
            part_code=f"WOP-SP-{suffix}",
            name="轴承",
            spec="6205",
            stock_quantity=10,
            safe_quantity=5,
        ),
    )
    order_ids: list[int] = []

    try:
        # ===== 场景 A：登记 + 完成，库存/流水/明细一致 =====
        order_a = work_order_service.create_work_order(
            db,
            WorkOrderCreate(warehouse_id=wh.id, device_id=device.id, title="更换轴承"),
        )
        order_ids.append(order_a.id)
        _transition(db, order_a.id, "assign", assignee_id=user.id)
        _transition(db, order_a.id, "start")

        work_order_service.add_part_to_order(
            db, order_a.id, WorkOrderPartAdd(spare_part_id=part.id, quantity=3)
        )
        work_order_service.add_part_to_order(
            db, order_a.id, WorkOrderPartAdd(spare_part_id=part.id, quantity=2)
        )
        parts = work_order_service.list_order_parts(db, order_a.id)
        assert len(parts) == 1 and parts[0]["quantity"] == 5, f"累加失败: {parts}"
        print("[验证① 登记累加] 3+2 → 单条明细 5 OK")

        _transition(db, order_a.id, "submit")
        _transition(db, order_a.id, "complete", result="已更换")
        db.refresh(part)
        assert part.stock_quantity == 5
        wo_record = db.scalar(
            select(StockRecord).where(
                StockRecord.related_work_order_id == order_a.id,
                StockRecord.change_type == "WORK_ORDER",
            )
        )
        assert wo_record is not None
        assert wo_record.quantity == -5 and wo_record.balance_after == 5
        print("[验证② 完成扣减] 库存 10→5，WORK_ORDER 流水(-5,余量5) 与明细一致 OK")

        # ===== 场景 B：库存不足完成被拒绝 =====
        order_b = work_order_service.create_work_order(
            db,
            WorkOrderCreate(warehouse_id=wh.id, device_id=device.id, title="领用轴承"),
        )
        order_ids.append(order_b.id)
        _transition(db, order_b.id, "assign", assignee_id=user.id)
        _transition(db, order_b.id, "start")
        work_order_service.add_part_to_order(
            db, order_b.id, WorkOrderPartAdd(spare_part_id=part.id, quantity=6)
        )
        _transition(db, order_b.id, "submit")
        try:
            _transition(db, order_b.id, "complete")
            raise AssertionError("库存不足仍完成工单")
        except HTTPException as e:
            assert e.status_code == 400 and "库存不足" in str(e.detail)
        db.refresh(part)
        assert part.stock_quantity == 5, "失败后库存被扣"
        order_b = db.get(WorkOrder, order_b.id)
        assert order_b.status == "PENDING_ACCEPT", "失败后状态不应变为 COMPLETED"
        wo_records_b = db.scalars(
            select(StockRecord).where(StockRecord.related_work_order_id == order_b.id)
        ).all()
        assert len(wo_records_b) == 0, "失败后产生流水"
        print("[验证③ 库存不足] 400 拒绝，库存 5 / 状态 PENDING_ACCEPT / 无流水 OK")

        # ===== 场景 C：取消回滚明细 =====
        order_c = work_order_service.create_work_order(
            db,
            WorkOrderCreate(warehouse_id=wh.id, device_id=device.id, title="临时领用"),
        )
        order_ids.append(order_c.id)
        _transition(db, order_c.id, "assign", assignee_id=user.id)
        _transition(db, order_c.id, "start")
        work_order_service.add_part_to_order(
            db, order_c.id, WorkOrderPartAdd(spare_part_id=part.id, quantity=2)
        )
        _transition(db, order_c.id, "cancel")
        db.refresh(part)
        assert part.stock_quantity == 5, "取消后库存被扣"
        remaining = db.scalar(
            select(func.count(WorkOrderPart.id)).where(WorkOrderPart.work_order_id == order_c.id)
        )
        assert remaining == 0, "取消后明细未清"
        print("[验证④ 取消回滚] 明细已清，库存未扣（仍 5）OK")

        print("\n========== 工单消耗备件测试全部通过 ==========")
    finally:
        db.rollback()
        for oid in order_ids:
            db.query(Notification).filter(
                Notification.ref_type == "WORK_ORDER",
                Notification.ref_id == oid,
            ).delete()
            db.query(WorkOrderPart).filter(WorkOrderPart.work_order_id == oid).delete()
            db.query(StockRecord).filter(StockRecord.related_work_order_id == oid).delete()
            db.query(WorkOrder).filter(WorkOrder.id == oid).delete()
        db.query(SysUser).filter(SysUser.id == user.id).delete()
        db.query(StockRecord).filter(StockRecord.spare_part_id == part.id).delete()
        db.query(SparePart).filter(SparePart.id == part.id).delete()
        db.query(Device).filter(Device.id == device.id).delete()
        db.query(Warehouse).filter(Warehouse.id == wh.id).delete()
        db.commit()
        db.close()


if __name__ == "__main__":
    test_work_order_part_flow()
