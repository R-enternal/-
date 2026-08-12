"""重建监测演示数据：清空传感器/健康度/告警，按低频故障参数重新生成 24 小时"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.monitor import Alert, HealthRecord, SensorData  # noqa: E402
from app.services import health_service, sensor_service  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        # 1. 清空监测数据（保留已转工单的告警，避免悬空引用）
        db.execute(delete(SensorData))
        db.execute(delete(HealthRecord))
        db.execute(delete(Alert).where(Alert.status != "CONVERTED"))
        db.commit()
        print("已清空 sensor_data / health_record / 非已转工单告警")

        # 2. 重新生成 24 小时模拟数据（低频故障：正常期 12~24h）
        result = sensor_service.generate_history(db, minutes=1440)
        print(f"已生成 {result['rows']} 条传感器数据（{result['points']} 个点位 × 24h）")

        # 3. 触发一次健康度计算，让看板有当前健康度
        health = health_service.compute_all_health(db)
        print(f"健康度已计算：{health['devices']} 台设备，{health['records']} 条记录")
    finally:
        db.close()


if __name__ == "__main__":
    main()
