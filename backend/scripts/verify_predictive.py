"""预测性告警验收：Holt 平滑单测 + 端到端判定"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select  # noqa: E402

from app.core.predictive_engine import check_predictive  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.device import DevicePoint  # noqa: E402
from app.models.monitor import Alert, SensorData  # noqa: E402
from app.services import alert_service  # noqa: E402


def test_pure() -> None:
    # 1. 持续上升 → PREDICTIVE_HIGH，ETA 合理
    rising = [50.0 + i * 1.5 for i in range(30)]
    r = check_predictive(alarm_low=None, alarm_high=85.0, recent_values=rising, horizon=12, window=20)
    assert r is not None and r.alert_type == "PREDICTIVE_HIGH", f"上升未触发: {r}"
    assert 1 <= r.eta_steps <= 40, f"ETA 不合理: {r.eta_steps}"
    print(f"[单测① 上升预测] PREDICTIVE_HIGH 触发，预测值 {r.predicted_value}，ETA {r.eta_steps} 步 OK")

    # 2. 平稳序列 → 不触发
    flat = [50.0] * 30
    assert (
        check_predictive(alarm_low=None, alarm_high=85.0, recent_values=flat, horizon=12, window=20)
        is None
    )
    print("[单测② 平稳序列] 不触发 OK")

    # 3. 持续下降 → PREDICTIVE_LOW
    falling = [80.0 - i * 2.0 for i in range(30)]
    r = check_predictive(
        alarm_low=30.0, alarm_high=None, recent_values=falling, horizon=12, window=20
    )
    assert r is not None and r.alert_type == "PREDICTIVE_LOW", f"下降未触发: {r}"
    print(f"[单测③ 下降预测] PREDICTIVE_LOW 触发，预测值 {r.predicted_value} OK")


def test_e2e() -> None:
    db = SessionLocal()
    try:
        point = db.scalar(
            select(DevicePoint)
            .where(DevicePoint.point_type == "TEMPERATURE")
            .order_by(DevicePoint.id)
            .limit(1)
        )
        assert point is not None and point.alarm_high, "找不到带温度上限的点位"
        now = datetime.now().replace(microsecond=0)
        # 插入 30 条持续上升数据（当前时间往前 30 分钟）
        base = point.alarm_high * 0.5
        rows = []
        for i in range(30):
            rows.append(
                SensorData(
                    device_id=point.device_id,
                    device_point_id=point.id,
                    value=round(base + i * (point.alarm_high * 0.03), 3),
                    status="NORMAL",
                    collected_at=now - timedelta(minutes=29 - i),
                )
            )
        db.add_all(rows)
        db.commit()

        result = alert_service.check_all_points(db)
        print(f"[端到端] 判定完成：检查 {result['points']} 点位，新增 {result['created']} 告警")

        pred = db.scalar(
            select(Alert).where(
                Alert.point_id == point.id,
                Alert.alert_type.in_(["PREDICTIVE_HIGH", "PREDICTIVE_LOW"]),
            )
        )
        assert pred is not None, "未生成预测告警"
        print(f"[端到端] 预测告警: {pred.title} | {pred.description}")

        # 清理测试数据（避免污染看板/告警中心）
        db.execute(delete(Alert).where(Alert.id == pred.id))
        db.execute(
            delete(SensorData).where(
                SensorData.device_point_id == point.id, SensorData.collected_at >= now - timedelta(minutes=30)
            )
        )
        db.commit()
        print("[端到端] 测试数据已清理")
    finally:
        db.close()


def main() -> None:
    test_pure()
    test_e2e()
    print("\n========== 预测性告警验收通过 ==========")


if __name__ == "__main__":
    main()
