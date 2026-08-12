"""清理 pytest 测试残留的设备与关联数据（保留 4 台演示设备 290-293）

用法（backend 目录下）：python scripts/cleanup_test_devices.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select, update  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.agent import MaintenanceBusyWindow, MaintenancePlan  # noqa: E402
from app.models.device import Device, DevicePoint  # noqa: E402
from app.models.monitor import Alert, HealthRecord, SensorData  # noqa: E402
from app.models.warehouse import Warehouse  # noqa: E402
from app.models.work_order import WorkOrder, WorkOrderPart  # noqa: E402
from app.services import health_service  # noqa: E402

TEST_DEVICE_IDS = (299, 316, 333, 350, 367)
TEST_WAREHOUSE_IDS = (245, 261, 277, 293, 309)


def main() -> None:
    db = SessionLocal()
    try:
        # 1. 先解除维保计划对工单的引用，再删计划与工单（避免外键冲突）
        order_ids = tuple(
            db.scalars(select(WorkOrder.id).where(WorkOrder.device_id.in_(TEST_DEVICE_IDS))).all()
        )
        if order_ids:
            db.execute(
                update(MaintenancePlan)
                .where(MaintenancePlan.work_order_id.in_(order_ids))
                .values(work_order_id=None)
            )
        db.execute(delete(MaintenancePlan).where(MaintenancePlan.device_id.in_(TEST_DEVICE_IDS)))
        if order_ids:
            db.execute(delete(WorkOrderPart).where(WorkOrderPart.work_order_id.in_(order_ids)))
            db.execute(delete(WorkOrder).where(WorkOrder.id.in_(order_ids)))
        # 2. 监测数据
        db.execute(delete(Alert).where(Alert.device_id.in_(TEST_DEVICE_IDS)))
        db.execute(delete(HealthRecord).where(HealthRecord.device_id.in_(TEST_DEVICE_IDS)))
        db.execute(delete(SensorData).where(SensorData.device_id.in_(TEST_DEVICE_IDS)))
        db.execute(delete(DevicePoint).where(DevicePoint.device_id.in_(TEST_DEVICE_IDS)))
        db.execute(delete(Device).where(Device.id.in_(TEST_DEVICE_IDS)))
        # 4. 测试仓库及其忙闲时段
        db.execute(
            delete(MaintenanceBusyWindow).where(
                MaintenanceBusyWindow.warehouse_id.in_(TEST_WAREHOUSE_IDS)
            )
        )
        db.execute(delete(Warehouse).where(Warehouse.id.in_(TEST_WAREHOUSE_IDS)))
        db.commit()
        print(f"已清理测试设备 {len(TEST_DEVICE_IDS)} 台及关联数据")

        # 5. 重算演示设备健康度
        result = health_service.compute_all_health(db)
        print(f"健康度重算：{result['devices']} 台设备")
    finally:
        db.close()


if __name__ == "__main__":
    main()
