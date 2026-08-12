"""阈值告警逻辑验收测试

第一部分：纯函数单测（不依赖数据库）——防抖/分级/上下限
第二部分：集成测试——构造连续超限数据，验证告警生成、去重、证据字段

运行方式（backend 目录下）：python scripts/test_threshold.py
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.core.threshold_engine import check_threshold  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.device import Device, DevicePoint  # noqa: E402
from app.models.monitor import Alert, SensorData  # noqa: E402
from app.models.warehouse import Warehouse  # noqa: E402
from app.services import alert_service  # noqa: E402


def test_pure_function() -> None:
    """纯函数单测：防抖、分级、上下限"""
    # 1. 连续 3 条超上限 → 告警（WARNING）
    r = check_threshold(alarm_low=None, alarm_high=50.0, recent_values=[55.0, 56.0, 57.0])
    assert r is not None and r.alert_type == "THRESHOLD_HIGH"
    assert r.level == "WARNING" and r.metric_value == 57.0 and r.threshold == 50.0
    print("[纯函数① 连续3次超上限] THRESHOLD_HIGH / WARNING OK")

    # 2. 超限幅度 >20% → CRITICAL
    r = check_threshold(alarm_low=None, alarm_high=50.0, recent_values=[60.0, 61.0, 62.0])
    assert r is not None and r.level == "CRITICAL"
    print("[纯函数② 超限>20%] CRITICAL OK")

    # 3. 2 条超限 + 1 条正常 → 不告警（防抖）
    r = check_threshold(alarm_low=None, alarm_high=50.0, recent_values=[55.0, 56.0, 45.0])
    assert r is None
    print("[纯函数③ 2超1正常] 不告警 OK")

    # 4. 数据不足 3 条 → 不告警
    r = check_threshold(alarm_low=None, alarm_high=50.0, recent_values=[55.0, 56.0])
    assert r is None
    print("[纯函数④ 数据不足] 不告警 OK")

    # 5. 连续 3 条低于下限 → THRESHOLD_LOW
    r = check_threshold(alarm_low=10.0, alarm_high=None, recent_values=[5.0, 4.0, 3.0])
    assert r is not None and r.alert_type == "THRESHOLD_LOW"
    print("[纯函数⑤ 连续3次低于下限] THRESHOLD_LOW OK")


def test_integration() -> None:
    """集成测试：数据库链路（构造数据 → 判定 → 告警 → 去重 → 清理）"""
    db = SessionLocal()
    run_suffix = str(int(datetime.now().timestamp()))

    # 1. 构造测试数据：仓库 + 设备 + 点位（低阈值便于构造超限）+ 3 条超限数据
    wh = Warehouse(name=f"测试仓-{run_suffix}")
    db.add(wh)
    db.flush()
    device = Device(
        warehouse_id=wh.id,
        device_code=f"TH-{run_suffix}",
        name="阈值测试设备",
        device_type="CONVEYOR",
    )
    db.add(device)
    db.flush()
    point = DevicePoint(
        device_id=device.id,
        point_code="TH-TEMP",
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

    try:
        # 2. 触发判定
        result = alert_service.check_all_points(db)
        assert result["created"] >= 1

        # 3. 验证测试点位告警记录完整
        alert = db.scalar(select(Alert).where(Alert.point_id == point.id))
        assert alert is not None
        assert alert.device_id == device.id
        assert alert.alert_type == "THRESHOLD_HIGH"
        assert alert.trigger_layer == "THRESHOLD"
        assert alert.metric_value == 62.0
        assert alert.threshold == 50.0
        assert alert.status == "PENDING"
        assert alert.description and "连续" in alert.description
        print(
            f"[集成① 告警生成] {alert.alert_type} 实际值={alert.metric_value} "
            f"阈值={alert.threshold} 描述={alert.description} OK"
        )

        # 4. 再触发一次 → 不重复生成（去重）
        alert_service.check_all_points(db)
        count = db.scalar(select(func.count(Alert.id)).where(Alert.point_id == point.id))
        assert count == 1, f"去重失效，告警数 {count}"
        print("[集成② 去重] 再次检查未重复生成 OK")
    finally:
        # 5. 清理测试数据（先删子表，再删主表）
        db.query(SensorData).filter(SensorData.device_point_id == point.id).delete()
        db.query(Alert).filter(Alert.point_id == point.id).delete()
        db.query(DevicePoint).filter(DevicePoint.id == point.id).delete()
        db.query(Device).filter(Device.id == device.id).delete()
        db.query(Warehouse).filter(Warehouse.id == wh.id).delete()
        db.commit()
        db.close()


def test_threshold_flow() -> None:
    test_pure_function()
    test_integration()
    print("\n========== 阈值告警测试全部通过 ==========")


if __name__ == "__main__":
    test_threshold_flow()
