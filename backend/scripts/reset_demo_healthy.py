"""演示数据重排：大部分设备健康，仅 1~2 台有故障

流程：清空监测数据 → 生成 24h 正常数据 → 对指定设备注入异常
      → 触发告警判定 + 健康度计算
"""

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select, update  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.device import Device, DevicePoint  # noqa: E402
from app.models.monitor import Alert, HealthRecord, SensorData  # noqa: E402
from app.models.work_order import WorkOrder  # noqa: E402
from app.services import alert_service, health_service, sensor_service  # noqa: E402


def inject_anomaly(db, device: Device, point_type: str, base: float, peak: float, minutes: int) -> None:
    """给设备某个点位注入一段由正常爬升到超限的异常数据（每分钟一条）"""
    point = db.scalar(
        select(DevicePoint).where(
            DevicePoint.device_id == device.id, DevicePoint.point_type == point_type
        )
    )
    if point is None:
        print(f"  跳过：{device.name} 无 {point_type} 点位")
        return
    now = datetime.now().replace(microsecond=0)
    # 先清掉该点位最近 minutes 分钟的正常数据，避免与注入数据时间戳冲突
    db.execute(
        delete(SensorData).where(
            SensorData.device_point_id == point.id,
            SensorData.collected_at >= now - timedelta(minutes=minutes + 2),
        )
    )
    db.flush()
    rows = []
    for i in range(minutes):
        ratio = i / (minutes - 1)
        value = base + (peak - base) * ratio + random.gauss(0, 0.3)
        rows.append(
            SensorData(
                device_id=device.id,
                device_point_id=point.id,
                value=round(max(value, 0.0), 3),
                status="NORMAL",
                collected_at=now - timedelta(seconds=(minutes - 1 - i) * 60),
            )
        )
    db.add_all(rows)
    print(f"  注入 {device.name} {point_type}：{base} → {peak}（{minutes} 分钟）")


def main() -> None:
    random.seed(7)
    db = SessionLocal()
    try:
        # 1. 清空监测数据
        db.execute(update(WorkOrder).values(alert_id=None))
        db.execute(delete(SensorData))
        db.execute(delete(HealthRecord))
        db.execute(delete(Alert))
        db.commit()
        print("已清空 sensor_data / health_record / alert")

        # 2. 生成 24h 正常数据（低频故障，绝大多数点位保持正常）
        result = sensor_service.generate_history(db, minutes=1440)
        print(f"已生成 {result['rows']} 条正常数据")

        # 3. 给 1~2 台设备注入故障
        devices = {d.name: d for d in db.scalars(select(Device)).all()}
        inject_anomaly(db, devices["1号分拣机"], "TEMPERATURE", base=62.0, peak=92.5, minutes=90)
        inject_anomaly(db, devices["AGV搬运车"], "VIBRATION", base=3.0, peak=8.6, minutes=60)
        db.commit()

        # 4. 告警判定 + 健康度计算
        alerts = alert_service.check_all_points(db)
        print(f"告警判定：检查 {alerts['points']} 点位，新增 {alerts['created']} 条告警")
        health = health_service.compute_all_health(db)
        print(f"健康度计算：{health['devices']} 台设备")
    finally:
        db.close()


if __name__ == "__main__":
    main()
