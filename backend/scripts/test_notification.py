"""通知中心验收测试

验证项：
1. 告警生成 → ALERT 通知
2. 备件低于安全库存 → STOCK 通知
3. 工单派单 → WORK_ORDER 通知（发给 ADMIN + 指派人）
4. 已读/未读/标记已读

前置：先运行 scripts/init_users.py 创建演示账号。
运行方式（backend 目录下）：python scripts/test_notification.py
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.device import Device, DevicePoint  # noqa: E402
from app.models.monitor import Alert, SensorData  # noqa: E402
from app.models.spare_part import SparePart, StockRecord  # noqa: E402
from app.models.user import Notification, SysUser  # noqa: E402
from app.models.warehouse import Warehouse  # noqa: E402
from app.models.work_order import WorkOrder  # noqa: E402
from app.schemas.spare_part import SparePartCreate, StockChangeRequest  # noqa: E402
from app.schemas.work_order import WorkOrderCreate, WorkOrderTransition  # noqa: E402
from app.services import (  # noqa: E402
    alert_service,
    notification_service,
    spare_part_service,
    work_order_service,
)


def test_notification_flow() -> None:
    db = SessionLocal()
    suffix = str(int(datetime.now().timestamp()))

    admin = db.scalar(select(SysUser).where(SysUser.username == "admin").limit(1))
    worker = db.scalar(select(SysUser).where(SysUser.username == "worker").limit(1))
    assert admin is not None and worker is not None, "请先运行 scripts/init_users.py"
    ref_ids: list[int] = []

    wh = Warehouse(name=f"通知测试仓-{suffix}")
    db.add(wh)
    db.flush()
    device = Device(
        warehouse_id=wh.id,
        device_code=f"NT-{suffix}",
        name="通知测试设备",
        device_type="CONVEYOR",
    )
    db.add(device)
    db.flush()
    point = DevicePoint(
        device_id=device.id,
        point_code="NT-TEMP",
        point_type="TEMPERATURE",
        unit="℃",
        alarm_high=50.0,
        trend_window=30,
        trend_delta=8.0,
    )
    db.add(point)
    db.flush()

    base_time = datetime.now().replace(microsecond=0)
    for i in range(3):
        db.add(
            SensorData(
                device_id=device.id,
                device_point_id=point.id,
                value=60.0 + i,
                collected_at=base_time - timedelta(minutes=2 - i),
            )
        )
    db.commit()

    order_id: int | None = None
    part_id: int | None = None

    try:
        # 1. 告警生成 → ALERT 通知
        alert_service.check_all_points(db)
        alert = db.scalar(select(Alert).where(Alert.point_id == point.id))
        assert alert is not None
        ref_ids.append(alert.id)
        alert_notices = db.scalars(
            select(Notification).where(
                Notification.ref_type == "ALERT",
                Notification.ref_id == alert.id,
            )
        ).all()
        assert len(alert_notices) >= 1 and all(n.notify_type == "ALERT" for n in alert_notices)
        print(f"[验证① 告警通知] ALERT 通知 {len(alert_notices)} 条（发给 ADMIN）OK")

        # 2. 备件低库存 → STOCK 通知
        part = spare_part_service.create_spare_part(
            db,
            SparePartCreate(
                warehouse_id=wh.id,
                part_code=f"NT-SP-{suffix}",
                name="低库存测试备件",
                stock_quantity=10,
                safe_quantity=10,
            ),
        )
        part_id = part.id
        ref_ids.append(part.id)
        part = spare_part_service.change_stock(
            db, part.id, StockChangeRequest(quantity=5), "OUTBOUND"
        )  # 10 → 5，穿越安全线 10 → 触发通知
        stock_notices = db.scalars(
            select(Notification).where(
                Notification.ref_type == "SPARE_PART",
                Notification.ref_id == part.id,
            )
        ).all()
        assert len(stock_notices) >= 1 and stock_notices[0].notify_type == "STOCK"
        print("[验证② 低库存通知] STOCK 通知（10 → 5 穿越安全线）OK")

        # 3. 工单派单 → WORK_ORDER 通知（ADMIN + 指派人）
        order = work_order_service.create_work_order(
            db,
            WorkOrderCreate(warehouse_id=wh.id, device_id=device.id, title="派单测试"),
        )
        order_id = order.id
        ref_ids.append(order.id)
        work_order_service.transition_work_order(
            db,
            order.id,
            WorkOrderTransition(action="assign", assignee_id=worker.id),
        )
        wo_notices = db.scalars(
            select(Notification).where(
                Notification.ref_type == "WORK_ORDER",
                Notification.ref_id == order.id,
            )
        ).all()
        receiver_ids = {n.user_id for n in wo_notices}
        assert admin.id in receiver_ids and worker.id in receiver_ids
        assert all(n.notify_type == "WORK_ORDER" for n in wo_notices)
        print(f"[验证③ 派单通知] WORK_ORDER 通知 {len(wo_notices)} 条（ADMIN + 指派人）OK")

        # 4. 已读/未读管理
        unread_before = notification_service.unread_count(db, admin.id)
        assert unread_before >= 3, f"未读数异常: {unread_before}"
        marked = notification_service.mark_read(db, admin.id)
        assert marked >= 3
        assert notification_service.unread_count(db, admin.id) == 0
        unread_list = notification_service.list_notifications(db, admin.id, is_read=False)
        assert len(unread_list) == 0
        read_list = notification_service.list_notifications(db, admin.id, is_read=True)
        assert len(read_list) >= 3
        print("[验证④ 已读管理] 全部标记已读，未读归零，列表过滤正确 OK")

        print("\n========== 通知中心测试全部通过 ==========")
    finally:
        db.rollback()
        # 清理通知（按 ref 删，覆盖 admin/worker 接收人）
        for rid in ref_ids:
            db.query(Notification).filter(
                Notification.ref_id == rid,
                Notification.ref_type.in_(["ALERT", "SPARE_PART", "WORK_ORDER"]),
            ).delete()
        if order_id is not None:
            db.query(WorkOrder).filter(WorkOrder.id == order_id).delete()
        if part_id is not None:
            db.query(StockRecord).filter(StockRecord.spare_part_id == part_id).delete()
            db.query(SparePart).filter(SparePart.id == part_id).delete()
        db.query(SensorData).filter(SensorData.device_id == device.id).delete()
        db.query(Alert).filter(Alert.device_id == device.id).delete()
        db.query(DevicePoint).filter(DevicePoint.id == point.id).delete()
        db.query(Device).filter(Device.id == device.id).delete()
        db.query(Warehouse).filter(Warehouse.id == wh.id).delete()
        db.commit()
        db.close()


if __name__ == "__main__":
    test_notification_flow()
