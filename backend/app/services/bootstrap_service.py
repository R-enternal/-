"""演示环境初始化：阈值模板、演示账号、数据库重置、演示数据"""

from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.agent import MaintenanceBusyWindow, MaintenancePlan
from app.models.device import (
    Device,
    DevicePoint,
    DeviceTypeThreshold,
    MaintenanceRecord,
)
from app.models.fusion import FusionDiagnosis
from app.models.kb import KbDocument
from app.models.monitor import Alert, HealthRecord, SensorData
from app.models.spare_part import SparePart, StockRecord
from app.models.user import Notification, SysUser
from app.models.warehouse import Warehouse
from app.models.work_order import WorkOrder, WorkOrderPart

# 设备类型阈值模板（行业经验值，ISO 10816 振动标准 + 轴承/电机温度经验）
TEMPLATES: dict[str, list[tuple]] = {
    "CONVEYOR": [
        ("VIBRATION", "mm/s", None, 7.1, 30, 2.0, 60),
        ("TEMPERATURE", "℃", None, 85.0, 30, 8.0, 60),
        ("CURRENT", "A", 0.5, 50.0, 30, 5.0, 60),
    ],
    "STACKER": [
        ("VIBRATION", "mm/s", None, 6.0, 30, 1.5, 60),
        ("TEMPERATURE", "℃", None, 80.0, 30, 8.0, 60),
        ("CURRENT", "A", 1.0, 80.0, 30, 8.0, 60),
    ],
    "AGV": [
        ("VIBRATION", "mm/s", None, 5.0, 30, 1.5, 60),
        ("TEMPERATURE", "℃", None, 75.0, 30, 8.0, 60),
        ("CURRENT", "A", 0.5, 30.0, 30, 5.0, 60),
    ],
    "SORTER": [
        ("VIBRATION", "mm/s", None, 6.5, 30, 2.0, 60),
        ("TEMPERATURE", "℃", None, 85.0, 30, 8.0, 60),
        ("CURRENT", "A", 0.5, 60.0, 30, 6.0, 60),
    ],
    "FORKLIFT": [
        ("VIBRATION", "mm/s", None, 7.0, 30, 2.0, 60),
        ("TEMPERATURE", "℃", None, 90.0, 30, 8.0, 60),
        ("CURRENT", "A", 0.5, 40.0, 30, 5.0, 60),
    ],
}


DEMO_USERS: list[dict] = [
    {"username": "admin", "password": "admin123", "real_name": "系统管理员", "role": "ADMIN"},
    {
        "username": "worker",
        "password": "worker123",
        "real_name": "维修工-张伟",
        "role": "MAINTENANCE_WORKER",
    },
    {"username": "viewer", "password": "viewer123", "real_name": "观察者-李静", "role": "VIEWER"},
]


def init_thresholds(db: Session) -> int:
    """灌入设备类型阈值模板（幂等：先清空再灌）"""
    db.execute(delete(DeviceTypeThreshold))
    for device_type, points in TEMPLATES.items():
        for (
            point_type,
            unit,
            alarm_low,
            alarm_high,
            window,
            delta,
            interval,
        ) in points:
            db.add(
                DeviceTypeThreshold(
                    device_type=device_type,
                    point_type=point_type,
                    unit=unit,
                    alarm_low_default=alarm_low,
                    alarm_high_default=alarm_high,
                    trend_window_default=window,
                    trend_delta_default=delta,
                    collect_interval_seconds_default=interval,
                )
            )
    db.commit()
    return len(TEMPLATES) * 3


def init_demo_users(db: Session) -> int:
    """初始化演示账号（幂等：已存在跳过）"""
    created = 0
    for item in DEMO_USERS:
        exists = db.scalar(select(SysUser.id).where(SysUser.username == item["username"]).limit(1))
        if exists is not None:
            continue
        db.add(
            SysUser(
                username=item["username"],
                password_hash=hash_password(item["password"]),
                real_name=item["real_name"],
                role=item["role"],
            )
        )
        created += 1
    db.commit()
    return created


def reset_database(db: Session) -> None:
    """清空全部业务表（保留 alembic_version），按外键依赖顺序删除"""
    for model in [
        MaintenancePlan,  # 外键引用 work_order / device / warehouse
        FusionDiagnosis,  # 外键引用 device
        Notification,
        WorkOrderPart,
        StockRecord,
        WorkOrder,
        MaintenanceBusyWindow,  # 外键引用 warehouse
        KbDocument,
        HealthRecord,
        Alert,
        SensorData,
        MaintenanceRecord,
        DevicePoint,
        SparePart,
        Device,
        Warehouse,
        SysUser,
        DeviceTypeThreshold,
    ]:
        db.execute(delete(model))
    db.commit()


def build_demo_data(db: Session) -> dict:
    """建演示仓库/设备/备件 → 补数据 → 触发告警/健康度 → 转一条工单"""
    from app.schemas.work_order import WorkOrderCreate
    from app.services import alert_service, health_service, sensor_service
    from app.services.work_order_service import create_from_alert, create_work_order

    # 1. 仓库 + 4 台不同类型设备（自动带点位）
    wh = Warehouse(
        name="合肥示范仓",
        address="合肥市经开区智能物流园",
        contact_name="王经理",
        contact_phone="13800000001",
    )
    db.add(wh)
    db.flush()

    devices = [
        (f"CV-{datetime.now():%H%M}", "1号输送线", "CONVEYOR", "A区01号"),
        ("ST-001", "1号堆垛机", "STACKER", "A区02号"),
        ("AGV-001", "AGV搬运车", "AGV", "B区"),
        ("SO-001", "1号分拣机", "SORTER", "C区01号"),
    ]
    for code, name, dtype, location in devices:
        device = Device(
            warehouse_id=wh.id,
            device_code=code,
            name=name,
            device_type=dtype,
            location=location,
        )
        db.add(device)
        db.flush()
        # 按模板自动创建点位
        for tpl in db.scalars(
            select(DeviceTypeThreshold).where(DeviceTypeThreshold.device_type == dtype)
        ).all():
            db.add(
                DevicePoint(
                    device_id=device.id,
                    point_code=f"{code}-{tpl.point_type.lower()}",
                    point_type=tpl.point_type,
                    unit=tpl.unit,
                    alarm_low=tpl.alarm_low_default,
                    alarm_high=tpl.alarm_high_default,
                    trend_window=tpl.trend_window_default,
                    trend_delta=tpl.trend_delta_default,
                )
            )
    db.commit()

    # 2. 备件（其中一个低库存）
    parts = [
        ("SP-001", "输送带", "B500", 8, 5, "A-01"),
        ("SP-002", "深沟球轴承", "6205", 3, 10, "A-02"),  # 低库存：3 < 10
        ("SP-003", "电机皮带轮", "SPB-200", 6, 4, "A-03"),
    ]
    for code, name, spec, stock, safe, loc in parts:
        db.add(
            SparePart(
                warehouse_id=wh.id,
                part_code=code,
                name=name,
                spec=spec,
                stock_quantity=stock,
                safe_quantity=safe,
                storage_location=loc,
            )
        )
    db.commit()

    # 3. 补 2 小时模拟数据
    sim = sensor_service.generate_history(db, minutes=120, seed=20260804)

    # 3.5 确定性异常注入：给第一台设备温度点位补 3 条超限数据，
    #     保证演示环境一定有告警（防抖需最新 3 条超限，不能依赖随机序列）
    demo_device = db.scalar(select(Device).order_by(Device.id).limit(1))
    if demo_device is not None:
        temp_point = db.scalar(
            select(DevicePoint)
            .where(
                DevicePoint.device_id == demo_device.id,
                DevicePoint.point_type == "TEMPERATURE",
            )
            .limit(1)
        )
        if temp_point is not None and temp_point.alarm_high is not None:
            now = datetime.now().replace(microsecond=0)
            for i in range(3):
                db.add(
                    SensorData(
                        device_id=demo_device.id,
                        device_point_id=temp_point.id,
                        value=temp_point.alarm_high + 10 + i,
                        collected_at=now - timedelta(minutes=2 - i),
                    )
                )
            db.commit()

    # 4. 触发告警 + 健康度
    alerts = alert_service.check_all_points(db)
    health = health_service.compute_all_health(db)

    # 5. 转一条 PENDING 告警为工单（让工单页有数据）
    pending = db.scalar(select(Alert).where(Alert.status == "PENDING").order_by(Alert.id).limit(1))
    order_count = 0
    if pending is not None:
        alert_service.handle_alert(
            db, pending.id, handled_by="admin", handle_note="已确认，安排维修"
        )
        create_from_alert(db, pending.id)
        order_count = 1
    else:
        # 兜底：手动建一条工单
        create_work_order(
            db,
            WorkOrderCreate(
                warehouse_id=wh.id,
                device_id=db.scalars(select(Device.id).limit(1)).first() or 1,
                title="例行巡检保养",
                description="演示用工单",
                order_type="MAINTENANCE",
                priority="MEDIUM",
                source="MANUAL",
            ),
        )
        order_count = 1

    return {
        "warehouses": 1,
        "devices": len(devices),
        "parts": len(parts),
        "sensor_rows": sim["rows"],
        "alerts": alerts["created"],
        "health_records": health["records"],
        "work_orders": order_count,
    }
