"""健康度评分验收测试

第一部分：纯函数单测——点位扣分、设备加权聚合、等级映射
第二部分：集成测试——构造设备+告警+数据，验证 health_record 写入与评分正确

运行方式（backend 目录下）：python scripts/test_health.py
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.health_score import (  # noqa: E402
    PointScore,
    aggregate_device,
    level_of,
    score_point,
)
from app.database import SessionLocal  # noqa: E402
from app.models.device import Device, DevicePoint  # noqa: E402
from app.models.monitor import Alert, HealthRecord, SensorData  # noqa: E402
from app.models.warehouse import Warehouse  # noqa: E402
from app.services import health_service  # noqa: E402


def test_pure_function() -> None:
    """纯函数单测"""
    # 1. 无告警无波动 → 100 分
    ps = score_point(
        point_id=1,
        point_type="VIBRATION",
        threshold_alert_level=None,
        has_trend_alert=False,
        has_predictive_alert=False,
        recent_values=[2.0] * 30,
        anomaly_score=0.0,
    )
    assert ps.score == 100.0 and ps.deductions == {}
    print("[纯函数① 正常点位] 100 分 OK")

    # 2. CRITICAL 阈值告警 → 扣 50
    ps = score_point(
        point_id=2,
        point_type="VIBRATION",
        threshold_alert_level="CRITICAL",
        has_trend_alert=False,
        has_predictive_alert=False,
        recent_values=[2.0] * 30,
        anomaly_score=0.0,
    )
    assert ps.score == 50.0 and ps.deductions["threshold_alert"] == 50.0
    print("[纯函数② 严重告警] 扣 50 → 50 分 OK")

    # 3. 高波动（CV 大）→ 稳定性扣分
    ps = score_point(
        point_id=3,
        point_type="TEMPERATURE",
        threshold_alert_level=None,
        has_trend_alert=False,
        has_predictive_alert=False,
        recent_values=[50.0 if i % 2 == 0 else 70.0 for i in range(30)],
        anomaly_score=0.0,
    )
    assert ps.score < 100.0 and "instability" in ps.deductions
    print(f"[纯函数③ 高波动] 稳定性扣 {ps.deductions['instability']} 分 OK")

    # 4. 异常分 0.8 → 异常扣分
    ps = score_point(
        point_id=4,
        point_type="CURRENT",
        threshold_alert_level=None,
        has_trend_alert=False,
        has_predictive_alert=False,
        recent_values=[20.0] * 30,
        anomaly_score=0.8,
    )
    assert ps.score < 100.0 and "anomaly" in ps.deductions
    print(f"[纯函数④ 异常分0.8] 扣 {ps.deductions['anomaly']} 分 OK")

    # 5. 设备聚合（振动 50 + 温度 100 + 电流 100，权重 6:3:1）→ 70
    device_score = aggregate_device(
        [
            PointScore(point_id=1, point_type="VIBRATION", score=50.0),
            PointScore(point_id=2, point_type="TEMPERATURE", score=100.0),
            PointScore(point_id=3, point_type="CURRENT", score=100.0),
        ]
    )
    assert device_score == 70.0
    print("[纯函数⑤ 设备聚合] 6:3:1 加权 → 70 分 OK")

    # 6. 等级映射
    assert (
        level_of(95) == "HEALTHY" and level_of(80) == "SUB_HEALTHY" and level_of(60) == "ABNORMAL"
    )
    print("[纯函数⑥ 等级映射] HEALTHY/SUB_HEALTHY/ABNORMAL OK")


def test_integration() -> None:
    """集成测试：设备 + 告警 + 数据 → health_record"""
    db = SessionLocal()
    run_suffix = str(int(datetime.now().timestamp()))

    wh = Warehouse(name=f"测试仓-{run_suffix}")
    db.add(wh)
    db.flush()
    device = Device(
        warehouse_id=wh.id,
        device_code=f"HL-{run_suffix}",
        name="健康度测试设备",
        device_type="CONVEYOR",
    )
    db.add(device)
    db.flush()

    point_specs = [
        ("HL-VIB", "VIBRATION", 7.1),
        ("HL-TEMP", "TEMPERATURE", 85.0),
        ("HL-CUR", "CURRENT", 50.0),
    ]
    points = []
    base_time = datetime.now().replace(microsecond=0)
    for code, ptype, high in point_specs:
        p = DevicePoint(
            device_id=device.id,
            point_code=code,
            point_type=ptype,
            unit="u",
            alarm_high=high,
            trend_window=30,
            trend_delta=8.0,
        )
        db.add(p)
        db.flush()
        points.append(p)
        # 灌 120 条稳定数据（让孤立森林有训练样本）
        for i in range(120):
            db.add(
                SensorData(
                    device_id=device.id,
                    device_point_id=p.id,
                    value=50.0 + (i % 5) * 0.1,
                    collected_at=base_time - timedelta(minutes=119 - i),
                )
            )

    # 给振动点位注入一条 CRITICAL 阈值告警（直接写表，不走判定）
    db.add(
        Alert(
            device_id=device.id,
            point_id=points[0].id,
            alert_type="THRESHOLD_HIGH",
            trigger_layer="THRESHOLD",
            level="CRITICAL",
            title="测试告警",
            metric_value=90.0,
            threshold=7.1,
            status="PENDING",
        )
    )
    db.commit()

    try:
        # 2. 计算健康度
        result = health_service.compute_all_health(db)
        assert result["records"] >= 1

        # 3. 验证测试设备的记录
        record = db.scalar(
            select(HealthRecord)
            .where(HealthRecord.device_id == device.id)
            .order_by(HealthRecord.computed_at.desc())
        )
        assert record is not None
        assert 0 <= record.score <= 100, f"评分越界: {record.score}"
        assert record.level in ("HEALTHY", "SUB_HEALTHY", "ABNORMAL")
        assert record.factor_json and "points" in record.factor_json
        print(
            f"[集成① 记录写入] device={record.device_id} score={record.score} "
            f"level={record.level} factor点位数={len(record.factor_json['points'])} OK"
        )

        # 4. 评分语义：振动有严重告警 → 振动分低，设备分应 < 100
        assert record.score < 100, "有严重告警但设备健康度没下降"
        print("[集成② 评分语义] 告警导致健康度下降 OK")
    finally:
        # 5. 清理
        db.rollback()  # 若计算阶段失败，先恢复会话再清理
        db.query(HealthRecord).filter(HealthRecord.device_id == device.id).delete()
        db.query(SensorData).filter(SensorData.device_id == device.id).delete()
        db.query(Alert).filter(Alert.device_id == device.id).delete()
        db.query(DevicePoint).filter(DevicePoint.device_id == device.id).delete()
        db.query(Device).filter(Device.id == device.id).delete()
        db.query(Warehouse).filter(Warehouse.id == wh.id).delete()
        db.commit()
        db.close()


def test_health_flow() -> None:
    test_pure_function()
    test_integration()
    print("\n========== 健康度测试全部通过 ==========")


if __name__ == "__main__":
    test_health_flow()
