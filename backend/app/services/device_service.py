"""设备域业务逻辑

核心设计（对齐企划书"开箱即用"承诺）：
新建设备时，根据 device_type_threshold 模板表自动生成传感器点位，
阈值/趋势参数/采集频率全部从模板带出，无需人工逐点配置。
"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.device import Device, DevicePoint, DeviceTypeThreshold, MaintenanceRecord
from app.models.warehouse import Warehouse
from app.schemas.device import (
    DeviceCreate,
    DevicePointCreate,
    DevicePointUpdate,
    DeviceUpdate,
)
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate

# ==================== 仓库 ====================


def list_warehouses(db: Session) -> list[Warehouse]:
    return list(db.scalars(select(Warehouse).order_by(Warehouse.id)))


def get_warehouse(db: Session, warehouse_id: int) -> Warehouse:
    wh = db.get(Warehouse, warehouse_id)
    if wh is None:
        raise HTTPException(status_code=404, detail=f"仓库不存在: {warehouse_id}")
    return wh


def create_warehouse(db: Session, data: WarehouseCreate) -> Warehouse:
    wh = Warehouse(**data.model_dump())
    db.add(wh)
    db.commit()
    db.refresh(wh)
    return wh


def update_warehouse(db: Session, warehouse_id: int, data: WarehouseUpdate) -> Warehouse:
    wh = get_warehouse(db, warehouse_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(wh, key, value)
    db.commit()
    db.refresh(wh)
    return wh


def delete_warehouse(db: Session, warehouse_id: int) -> None:
    wh = get_warehouse(db, warehouse_id)
    # 仓库下有设备时禁止删除（保护数据）
    has_device = db.scalar(select(Device.id).where(Device.warehouse_id == warehouse_id).limit(1))
    if has_device is not None:
        raise HTTPException(
            status_code=400,
            detail=f"仓库下仍有设备，无法删除（请先迁移或删除设备）: {warehouse_id}",
        )
    db.delete(wh)
    db.commit()


# ==================== 设备 ====================


def list_devices(
    db: Session,
    warehouse_id: int | None = None,
    device_type: str | None = None,
    status: str | None = None,
) -> list[Device]:
    stmt = select(Device).order_by(Device.id)
    if warehouse_id is not None:
        stmt = stmt.where(Device.warehouse_id == warehouse_id)
    if device_type:
        stmt = stmt.where(Device.device_type == device_type)
    if status:
        stmt = stmt.where(Device.status == status)
    return list(db.scalars(stmt))


def get_device(db: Session, device_id: int) -> Device:
    device = db.scalar(
        select(Device).where(Device.id == device_id).options(selectinload(Device.points))
    )
    if device is None:
        raise HTTPException(status_code=404, detail=f"设备不存在: {device_id}")
    return device


def create_device(db: Session, data: DeviceCreate) -> Device:
    """创建设备，并按模板自动带出传感器点位"""
    # 1. 校验仓库存在
    get_warehouse(db, data.warehouse_id)

    # 2. 校验设备编号唯一
    exists = db.scalar(select(Device.id).where(Device.device_code == data.device_code).limit(1))
    if exists is not None:
        raise HTTPException(status_code=400, detail=f"设备编号已存在: {data.device_code}")

    # 3. 创建设备
    device = Device(**data.model_dump(exclude={"auto_create_points"}))
    db.add(device)
    db.flush()  # 先拿到 device.id

    # 4. 按模板自动创建点位（企划书"开箱即用"核心逻辑）
    if data.auto_create_points:
        templates = db.scalars(
            select(DeviceTypeThreshold).where(DeviceTypeThreshold.device_type == data.device_type)
        ).all()
        if not templates:
            # 防静默失败：设备类型没有阈值模板时直接提示，避免建出"永远没数据"的设备
            raise HTTPException(
                status_code=400,
                detail=(
                    f"设备类型 {data.device_type} 暂无阈值模板，"
                    "请先运行 scripts/init_thresholds.py 或设置 auto_create_points=false"
                ),
            )
        for tpl in templates:
            db.add(
                DevicePoint(
                    device_id=device.id,
                    point_code=f"{data.device_code}-{tpl.point_type.lower()}",
                    point_type=tpl.point_type,
                    unit=tpl.unit,
                    alarm_low=tpl.alarm_low_default,
                    alarm_high=tpl.alarm_high_default,
                    trend_window=tpl.trend_window_default,
                    trend_delta=tpl.trend_delta_default,
                    collect_interval_seconds=tpl.collect_interval_seconds_default,
                )
            )

    db.commit()
    db.refresh(device)
    return get_device(db, device.id)


def update_device(db: Session, device_id: int, data: DeviceUpdate) -> Device:
    device = get_device(db, device_id)
    updates = data.model_dump(exclude_unset=True)
    # 设备编号查重（排除自身，避免改编号撞车导致 500）
    new_code = updates.get("device_code")
    if new_code is not None:
        exists = db.scalar(
            select(Device.id).where(Device.device_code == new_code, Device.id != device_id).limit(1)
        )
        if exists is not None:
            raise HTTPException(status_code=400, detail=f"设备编号已存在: {new_code}")
    # 更换设备类型时不自动重建点位（点位由用户手动管理）
    for key, value in updates.items():
        setattr(device, key, value)
    db.commit()
    db.refresh(device)
    return get_device(db, device_id)


def delete_device(db: Session, device_id: int) -> None:
    device = get_device(db, device_id)
    # 有维保记录则禁止删除（保护历史数据）
    has_record = db.scalar(
        select(MaintenanceRecord.id).where(MaintenanceRecord.device_id == device_id).limit(1)
    )
    if has_record is not None:
        raise HTTPException(
            status_code=400,
            detail=f"设备存在维保记录，无法删除（可改为 SCRAPPED 报废状态）: {device_id}",
        )
    db.delete(device)
    db.commit()


# ==================== 点位 ====================


def get_point(db: Session, point_id: int) -> DevicePoint:
    point = db.get(DevicePoint, point_id)
    if point is None:
        raise HTTPException(status_code=404, detail=f"点位不存在: {point_id}")
    return point


def list_points(db: Session, device_id: int) -> list[DevicePoint]:
    get_device(db, device_id)
    return list(
        db.scalars(
            select(DevicePoint).where(DevicePoint.device_id == device_id).order_by(DevicePoint.id)
        )
    )


def create_point(db: Session, device_id: int, data: DevicePointCreate) -> DevicePoint:
    get_device(db, device_id)
    exists = db.scalar(
        select(DevicePoint.id)
        .where(
            DevicePoint.device_id == device_id,
            DevicePoint.point_code == data.point_code,
        )
        .limit(1)
    )
    if exists is not None:
        raise HTTPException(
            status_code=400,
            detail=f"点位编号在该设备下已存在: {data.point_code}",
        )
    point = DevicePoint(device_id=device_id, **data.model_dump())
    db.add(point)
    db.commit()
    db.refresh(point)
    return point


def update_point(db: Session, point_id: int, data: DevicePointUpdate) -> DevicePoint:
    point = get_point(db, point_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(point, key, value)
    db.commit()
    db.refresh(point)
    return point


def delete_point(db: Session, point_id: int) -> None:
    point = get_point(db, point_id)
    db.delete(point)
    db.commit()
