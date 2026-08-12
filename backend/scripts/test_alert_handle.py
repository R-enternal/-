"""告警处理接口验收测试

验证项：
1. 确认告警：PENDING → HANDLED，handled_by/handled_at/handle_note 记录完整
2. 忽略告警：PENDING → IGNORED
3. 重复处理被拒绝（400）
4. 闭环：确认告警后重新计算健康度，设备评分回升

运行方式（backend 目录下）：python scripts/test_alert_handle.py
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.device import Device, DevicePoint  # noqa: E402
from app.models.monitor import Alert, HealthRecord, SensorData  # noqa: E402
from app.models.warehouse import Warehouse  # noqa: E402
from app.services import alert_service, health_service  # noqa: E402


def _build_device(db, suffix: str) -> tuple[Warehouse, Device, DevicePoint]:
    """构造测试设备（单振动点位，低阈值）"""
    wh = Warehouse(name=f"处理测试仓-{suffix}")
    db.add(wh)
    db.flush()
    device = Device(
        warehouse_id=wh.id,
        device_code=f"AH-{suffix}",
        name="告警处理测试设备",
        device_type="CONVEYOR",
    )
    db.add(device)
    db.flush()
    point = DevicePoint(
        device_id=device.id,
        point_code="AH-VIB",
        point_type="VIBRATION",
        unit="mm/s",
        alarm_high=7.1,
        trend_window=30,
        trend_delta=2.0,
    )
    db.add(point)
    db.flush()
    return wh, device, point


def _cleanup(db, wh, device, point) -> None:
    db.rollback()
    db.query(HealthRecord).filter(HealthRecord.device_id == device.id).delete()
    db.query(SensorData).filter(SensorData.device_id == device.id).delete()
    db.query(Alert).filter(Alert.device_id == device.id).delete()
    db.query(DevicePoint).filter(DevicePoint.id == point.id).delete()
    db.query(Device).filter(Device.id == device.id).delete()
    db.query(Warehouse).filter(Warehouse.id == wh.id).delete()
    db.commit()


def test_handle_and_ignore() -> None:
    """确认/忽略 + 字段完整 + 重复处理拒绝"""
    db = SessionLocal()
    suffix = str(int(datetime.now().timestamp()))
    wh, device, point = _build_device(db, suffix)

    def new_alert() -> Alert:
        a = Alert(
            device_id=device.id,
            point_id=point.id,
            alert_type="THRESHOLD_HIGH",
            trigger_layer="THRESHOLD",
            level="WARNING",
            title="测试告警",
            metric_value=9.0,
            threshold=7.1,
            status="PENDING",
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        return a

    try:
        # 1. 确认告警
        alert = new_alert()
        handled = alert_service.handle_alert(
            db, alert.id, handled_by="张工", handle_note="已现场检查，轴承正常"
        )
        assert handled.status == "HANDLED"
        assert handled.handled_by == "张工"
        assert handled.handled_at is not None
        assert handled.handle_note == "已现场检查，轴承正常"
        print("[验证① 确认告警] PENDING→HANDLED，处理人/时间/说明齐全 OK")

        # 2. 重复确认被拒绝
        try:
            alert_service.handle_alert(db, alert.id, handled_by="张工")
            raise AssertionError("重复确认未被拒绝")
        except HTTPException as e:
            assert e.status_code == 400
        print("[验证② 重复确认] 400 拒绝 OK")

        # 3. 忽略告警
        alert2 = new_alert()
        ignored = alert_service.ignore_alert(
            db, alert2.id, handled_by="李工", handle_note="传感器误报"
        )
        assert ignored.status == "IGNORED"
        assert ignored.handled_by == "李工"
        print("[验证③ 忽略告警] PENDING→IGNORED OK")

        # 4. 已忽略的再确认 → 拒绝
        try:
            alert_service.handle_alert(db, alert2.id)
            raise AssertionError("已忽略告警被确认")
        except HTTPException as e:
            assert e.status_code == 400
        print("[验证④ 已忽略不可确认] 400 拒绝 OK")
    finally:
        _cleanup(db, wh, device, point)
        db.close()


def test_health_recovery() -> None:
    """闭环：确认告警后健康度评分回升"""
    db = SessionLocal()
    suffix = str(int(datetime.now().timestamp()))
    wh, device, point = _build_device(db, suffix)

    # 灌 120 条稳定数据（孤立森林有训练样本，波动极小）
    base_time = datetime.now().replace(microsecond=0)
    for i in range(120):
        db.add(
            SensorData(
                device_id=device.id,
                device_point_id=point.id,
                value=2.0 + (i % 10) * 0.05,
                collected_at=base_time - timedelta(minutes=119 - i),
            )
        )
    # 注入 CRITICAL 告警
    db.add(
        Alert(
            device_id=device.id,
            point_id=point.id,
            alert_type="THRESHOLD_HIGH",
            trigger_layer="THRESHOLD",
            level="CRITICAL",
            title="严重告警",
            metric_value=20.0,
            threshold=7.1,
            status="PENDING",
        )
    )
    db.commit()

    try:
        # 1. 有告警时计算健康度
        health_service.compute_all_health(db)
        before = db.scalar(
            select(HealthRecord)
            .where(HealthRecord.device_id == device.id)
            .order_by(HealthRecord.computed_at.desc())
        )
        assert (
            before is not None and before.score < 70
        ), f"有告警评分应低: {before.score if before else None}"
        print(f"[闭环① 有告警] 评分 {before.score}（应 <70）OK")

        # 2. 确认告警
        alert = db.scalar(
            select(Alert).where(Alert.device_id == device.id, Alert.status == "PENDING")
        )
        alert_service.handle_alert(db, alert.id, handled_by="张工", handle_note="已处理")

        # 3. 重新计算健康度 → 评分回升
        health_service.compute_all_health(db)
        after = db.scalar(
            select(HealthRecord)
            .where(HealthRecord.device_id == device.id)
            .order_by(HealthRecord.computed_at.desc())
        )
        assert after is not None and after.score > before.score
        print(f"[闭环② 告警确认后] 评分 {before.score} → {after.score}，回升 OK")
    finally:
        _cleanup(db, wh, device, point)
        db.close()


def test_alert_handle_flow() -> None:
    test_handle_and_ignore()
    test_health_recovery()
    print("\n========== 告警处理测试全部通过 ==========")


if __name__ == "__main__":
    test_alert_handle_flow()
