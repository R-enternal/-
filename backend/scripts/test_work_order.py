"""工单基础流程验收测试

验证项：
1. 完整走一遍 创建→派单→执行→验收→完成
2. 非法跳转被拒绝（创建后直接验收/开始执行）
3. 取消：任意状态可取消，终态不可再流转
4. 列表按状态过滤

运行方式（backend 目录下）：python scripts/test_work_order.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.device import Device  # noqa: E402
from app.models.user import Notification, SysUser  # noqa: E402
from app.models.warehouse import Warehouse  # noqa: E402
from app.models.work_order import WorkOrder  # noqa: E402
from app.schemas.work_order import WorkOrderCreate, WorkOrderTransition  # noqa: E402
from app.services import work_order_service  # noqa: E402


def _build_ctx(db, suffix: str) -> tuple[Warehouse, Device, SysUser]:
    wh = Warehouse(name=f"工单测试仓-{suffix}")
    db.add(wh)
    db.flush()
    device = Device(
        warehouse_id=wh.id,
        device_code=f"WO-{suffix}",
        name="工单测试设备",
        device_type="CONVEYOR",
    )
    db.add(device)
    user = SysUser(
        username=f"wo_user_{suffix}",
        password_hash=hash_password("pass123"),
        real_name="工单测试用户",
        role="MAINTENANCE_WORKER",
    )
    db.add(user)
    db.commit()
    return wh, device, user


def _cleanup(db, wh, device, user, order_ids: list[int]) -> None:
    db.rollback()
    for oid in order_ids:
        db.query(Notification).filter(
            Notification.ref_type == "WORK_ORDER",
            Notification.ref_id == oid,
        ).delete()
        db.query(WorkOrder).filter(WorkOrder.id == oid).delete()
    db.query(SysUser).filter(SysUser.id == user.id).delete()
    db.query(Device).filter(Device.id == device.id).delete()
    db.query(Warehouse).filter(Warehouse.id == wh.id).delete()
    db.commit()


def test_work_order_flow() -> None:
    db = SessionLocal()
    suffix = str(int(datetime.now().timestamp()))
    wh, device, user = _build_ctx(db, suffix)
    order_ids: list[int] = []

    try:
        # 1. 创建工单
        order = work_order_service.create_work_order(
            db,
            WorkOrderCreate(
                warehouse_id=wh.id,
                device_id=device.id,
                title="输送机异响排查",
                description="1号输送线运行有异响",
                priority="HIGH",
            ),
        )
        order_ids.append(order.id)
        assert order.status == "PENDING_ASSIGN"
        assert order.order_no.startswith("WO")
        print(f"[验证① 创建] {order.order_no} 初始状态 PENDING_ASSIGN OK")

        # 2. 非法跳转：创建后直接验收 → 400
        for bad_action in ["complete", "start", "submit"]:
            try:
                work_order_service.transition_work_order(
                    db,
                    order.id,
                    WorkOrderTransition(action=bad_action),  # type: ignore[arg-type]
                )
                raise AssertionError(f"非法流转 {bad_action} 未被拒绝")
            except HTTPException as e:
                assert e.status_code == 400
        print("[验证② 非法跳转] 创建后直接验收/开始/提交全部 400 OK")

        # 3. 完整流程
        order = work_order_service.transition_work_order(
            db, order.id, WorkOrderTransition(action="assign", assignee_id=user.id)
        )
        assert order.status == "PENDING_EXECUTE"
        order = work_order_service.transition_work_order(
            db, order.id, WorkOrderTransition(action="start")
        )
        assert order.status == "IN_PROGRESS" and order.actual_start is not None
        order = work_order_service.transition_work_order(
            db, order.id, WorkOrderTransition(action="submit")
        )
        assert order.status == "PENDING_ACCEPT"
        order = work_order_service.transition_work_order(
            db, order.id, WorkOrderTransition(action="complete", result="更换轴承，运行正常")
        )
        assert order.status == "COMPLETED"
        assert order.actual_end is not None and order.result == "更换轴承，运行正常"
        print("[验证③ 完整流转] 创建→派单→执行→验收→完成 全链路 OK")

        # 4. 终态不可再流转
        try:
            work_order_service.transition_work_order(
                db, order.id, WorkOrderTransition(action="cancel")
            )
            raise AssertionError("已完成工单仍可取消")
        except HTTPException as e:
            assert e.status_code == 400
        print("[验证④ 终态锁定] COMPLETED 后取消被拒 OK")

        # 5. 取消流程
        order2 = work_order_service.create_work_order(
            db,
            WorkOrderCreate(
                warehouse_id=wh.id,
                device_id=device.id,
                title="临时工单",
            ),
        )
        order_ids.append(order2.id)
        order2 = work_order_service.transition_work_order(
            db, order2.id, WorkOrderTransition(action="cancel")
        )
        assert order2.status == "CANCELLED"
        print("[验证⑤ 取消] 任意状态可取消 OK")

        # 6. 列表过滤
        completed = work_order_service.list_work_orders(db, status="COMPLETED")
        assert any(o.id == order.id for o in completed)
        cancelled = work_order_service.list_work_orders(db, status="CANCELLED")
        assert any(o.id == order2.id for o in cancelled)
        by_device = work_order_service.list_work_orders(db, device_id=device.id)
        assert len(by_device) == 2
        print("[验证⑥ 列表过滤] 按状态/设备过滤 OK")

        print("\n========== 工单基础流程测试全部通过 ==========")
    finally:
        _cleanup(db, wh, device, user, order_ids)
        db.close()


if __name__ == "__main__":
    test_work_order_flow()
