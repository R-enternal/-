"""告警转工单验收测试

验证项：
1. PENDING 告警不允许直接转工单（必须先确认）
2. HANDLED 告警转工单：source=ALERT、alert_id 关联、标题/描述带出
3. 转后告警变 CONVERTED，重复转被拒绝
4. 工单详情中能看到来源告警信息

运行方式（backend 目录下）：python scripts/test_alert_convert.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.device import Device, DevicePoint  # noqa: E402
from app.models.monitor import Alert  # noqa: E402
from app.models.warehouse import Warehouse  # noqa: E402
from app.models.work_order import WorkOrder  # noqa: E402
from app.services import alert_service, work_order_service  # noqa: E402


def test_alert_convert_flow() -> None:
    db = SessionLocal()
    suffix = str(int(datetime.now().timestamp()))

    wh = Warehouse(name=f"转工单测试仓-{suffix}")
    db.add(wh)
    db.flush()
    device = Device(
        warehouse_id=wh.id,
        device_code=f"AC-{suffix}",
        name="转工单测试设备",
        device_type="CONVEYOR",
    )
    db.add(device)
    db.flush()
    point = DevicePoint(
        device_id=device.id,
        point_code="AC-TEMP",
        point_type="TEMPERATURE",
        unit="℃",
        alarm_high=85.0,
        trend_window=30,
        trend_delta=8.0,
    )
    db.add(point)
    db.flush()
    alert = Alert(
        device_id=device.id,
        point_id=point.id,
        alert_type="THRESHOLD_HIGH",
        trigger_layer="THRESHOLD",
        level="CRITICAL",
        title="TEMPERATURE 超限告警",
        description="连续 3 次采样超限，最近值 95.0，阈值 85.0",
        metric_value=95.0,
        threshold=85.0,
        status="PENDING",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    order_id: int | None = None

    try:
        # 1. PENDING 不允许直接转
        try:
            work_order_service.create_from_alert(db, alert.id)
            raise AssertionError("PENDING 告警被直接转工单")
        except HTTPException as e:
            assert e.status_code == 400
        print("[验证① PENDING 拦截] 未确认告警转工单 400 OK")

        # 2. 确认后转工单
        alert = alert_service.handle_alert(
            db, alert.id, handled_by="张工", handle_note="确认需要维修"
        )
        order = work_order_service.create_from_alert(db, alert.id)
        order_id = order.id
        assert order.source == "ALERT"
        assert order.alert_id == alert.id
        assert "超限告警" in order.title
        assert "95.0" in order.description and "确认需要维修" in order.description
        assert order.status == "PENDING_ASSIGN"
        print(f"[验证② 转工单] {order.order_no} source=ALERT，标题/描述/备注带出 OK")

        # 3. 转后告警变 CONVERTED，重复转被拒绝
        refreshed = db.get(Alert, alert.id)
        assert refreshed is not None and refreshed.status == "CONVERTED"
        try:
            work_order_service.create_from_alert(db, alert.id)
            raise AssertionError("重复转工单未被拒绝")
        except HTTPException as e:
            assert e.status_code == 400
        print("[验证③ CONVERTED] 重复转工单 400 OK")

        # 4. 工单详情带来源告警信息
        detail = work_order_service.work_order_with_names(db, order)
        assert detail["alert_info"] is not None
        assert detail["alert_info"]["alert_type"] == "THRESHOLD_HIGH"
        assert detail["alert_info"]["level"] == "CRITICAL"
        print("[验证④ 来源告警] 工单详情含 alert_info OK")

        print("\n========== 告警转工单测试全部通过 ==========")
    finally:
        db.rollback()
        if order_id is not None:
            db.query(WorkOrder).filter(WorkOrder.id == order_id).delete()
        db.query(Alert).filter(Alert.id == alert.id).delete()
        db.query(DevicePoint).filter(DevicePoint.id == point.id).delete()
        db.query(Device).filter(Device.id == device.id).delete()
        db.query(Warehouse).filter(Warehouse.id == wh.id).delete()
        db.commit()
        db.close()


if __name__ == "__main__":
    test_alert_convert_flow()
