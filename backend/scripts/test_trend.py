"""趋势告警逻辑验收测试

第一部分：纯函数单测——持续上升触发 / 平缓不触发 / 下降不触发 / 数据不足
第二部分：集成测试——构造持续上升数据，验证 TREND 告警生成、与阈值告警区分、去重

运行方式（backend 目录下）：python scripts/test_trend.py
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.core.trend_engine import check_trend  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.device import Device, DevicePoint  # noqa: E402
from app.models.monitor import Alert, SensorData  # noqa: E402
from app.models.warehouse import Warehouse  # noqa: E402
from app.services import alert_service  # noqa: E402


def test_pure_function() -> None:
    """纯函数单测"""
    # 1. 持续上升（30 条 50→80）→ 触发 TREND
    rising = [50.0 + i for i in range(30)]
    r = check_trend(recent_values=rising, trend_delta=5.0, trend_window=30)
    assert r is not None and r.alert_type == "TREND"
    assert r.slope > 0 and r.rise_amount >= 5.0
    print(f"[纯函数① 持续上升] TREND OK（斜率={r.slope} 上升={r.rise_amount}）")

    # 2. 平缓波动 → 不触发
    flat = [50.0 + (i % 3) * 0.5 for i in range(30)]
    r = check_trend(recent_values=flat, trend_delta=5.0, trend_window=30)
    assert r is None
    print("[纯函数② 平缓波动] 不触发 OK")

    # 3. 持续下降 → 不触发（当前只做上升趋势）
    falling = [80.0 - i for i in range(30)]
    r = check_trend(recent_values=falling, trend_delta=5.0, trend_window=30)
    assert r is None
    print("[纯函数③ 持续下降] 不触发 OK")

    # 4. 数据不足（少于 MIN_WINDOW=5）→ 不触发
    r = check_trend(recent_values=[1.0, 2.0, 3.0, 4.0], trend_delta=1.0, trend_window=10)
    assert r is None
    print("[纯函数④ 数据不足] 不触发 OK")

    # 5. 上升但幅度不足 → 不触发
    small_rise = [50.0 + i * 0.2 for i in range(30)]  # 总上升 5.8 > 5？0.2*29=5.8
    r = check_trend(recent_values=small_rise, trend_delta=6.0, trend_window=30)
    assert r is None
    print("[纯函数⑤ 幅度不足] 不触发 OK")


def test_integration() -> None:
    """集成测试：构造持续上升数据 → TREND 告警 + 类型区分 + 去重"""
    db = SessionLocal()
    run_suffix = str(int(datetime.now().timestamp()))

    # 1. 构造测试数据：高阈值点位（避免阈值告警干扰），小窗口便于构造
    wh = Warehouse(name=f"测试仓-{run_suffix}")
    db.add(wh)
    db.flush()
    device = Device(
        warehouse_id=wh.id,
        device_code=f"TR-{run_suffix}",
        name="趋势测试设备",
        device_type="CONVEYOR",
    )
    db.add(device)
    db.flush()
    point = DevicePoint(
        device_id=device.id,
        point_code="TR-TEMP",
        point_type="TEMPERATURE",
        unit="℃",
        alarm_high=200.0,  # 高阈值，确保不触发阈值告警
        trend_window=10,
        trend_delta=5.0,
    )
    db.add(point)
    db.flush()

    # 2. 灌入 15 条持续上升数据（50 → 64），窗口内上升远超 5
    base_time = datetime.now().replace(microsecond=0)
    for i in range(15):
        db.add(
            SensorData(
                device_id=device.id,
                device_point_id=point.id,
                value=50.0 + i,
                collected_at=base_time - timedelta(minutes=14 - i),
            )
        )
    db.commit()

    try:
        # 3. 触发双判定
        alert_service.check_all_points(db)

        # 4. 验证生成了 TREND 告警（且不是阈值告警）
        alert = db.scalar(select(Alert).where(Alert.point_id == point.id))
        assert alert is not None
        assert alert.alert_type == "TREND", f"期望 TREND，实际 {alert.alert_type}"
        assert alert.trigger_layer == "TREND"
        assert alert.level == "WARNING"
        assert alert.metric_value == 64.0
        assert alert.threshold == 5.0
        assert "上升" in alert.description
        print(
            f"[集成① 趋势告警生成] {alert.alert_type} 当前值={alert.metric_value} "
            f"阈值={alert.threshold} 描述={alert.description} OK"
        )

        # 5. 类型区分：同点位不应存在阈值告警（高阈值 + 数值未越线）
        threshold_alerts = db.scalars(
            select(Alert).where(
                Alert.point_id == point.id,
                Alert.alert_type.like("THRESHOLD%"),
            )
        ).all()
        assert len(threshold_alerts) == 0
        print("[集成② 类型区分] 无阈值告警混入 OK")

        # 6. 去重：再次检查不新增
        alert_service.check_all_points(db)
        count = db.scalar(
            select(func.count(Alert.id)).where(
                Alert.point_id == point.id, Alert.alert_type == "TREND"
            )
        )
        assert count == 1, f"趋势告警去重失效，数量 {count}"
        print("[集成③ 去重] 再次检查未重复生成 OK")
    finally:
        # 7. 清理
        db.query(SensorData).filter(SensorData.device_point_id == point.id).delete()
        db.query(Alert).filter(Alert.point_id == point.id).delete()
        db.query(DevicePoint).filter(DevicePoint.id == point.id).delete()
        db.query(Device).filter(Device.id == device.id).delete()
        db.query(Warehouse).filter(Warehouse.id == wh.id).delete()
        db.commit()
        db.close()


def test_trend_flow() -> None:
    test_pure_function()
    test_integration()
    print("\n========== 趋势告警测试全部通过 ==========")


if __name__ == "__main__":
    test_trend_flow()
