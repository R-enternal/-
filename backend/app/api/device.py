"""设备与点位路由"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.schemas.common import ok
from app.schemas.device import (
    DeviceCreate,
    DeviceOut,
    DevicePointCreate,
    DevicePointOut,
    DevicePointUpdate,
    DeviceUpdate,
    DeviceWithPointsOut,
)
from app.services import device_service, sensor_service

router = APIRouter(prefix="/api/devices", tags=["设备"])


def _device_out(device: Device) -> dict:
    return DeviceOut.model_validate(device).model_dump()


def _device_with_points_out(device: Device) -> dict:
    return DeviceWithPointsOut.model_validate(device).model_dump()


@router.get("")
def list_devices(
    warehouse_id: int | None = None,
    device_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """设备列表（支持按仓库/类型/状态过滤）"""
    items = device_service.list_devices(db, warehouse_id, device_type, status)
    return ok(data=[_device_out(d) for d in items])


@router.get("/{device_id}")
def get_device(device_id: int, db: Session = Depends(get_db)) -> dict:
    """设备详情（含点位列表）"""
    device = device_service.get_device(db, device_id)
    return ok(data=_device_with_points_out(device))


@router.get("/{device_id}/sensor-data")
def list_sensor_data(
    device_id: int,
    point_id: int | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> dict:
    """设备传感器时序数据（按时间正序返回最近 limit 条，供曲线图使用）"""
    device_service.get_device(db, device_id)  # 404 兜底
    items = sensor_service.list_recent_sensor_data(
        db, device_id=device_id, point_id=point_id, limit=limit
    )
    return ok(data=items)


@router.post("")
def create_device(data: DeviceCreate, db: Session = Depends(get_db)) -> dict:
    """新建设备（默认按类型模板自动创建传感器点位）"""
    device = device_service.create_device(db, data)
    return ok(data=_device_with_points_out(device), message="设备创建成功")


@router.put("/{device_id}")
def update_device(device_id: int, data: DeviceUpdate, db: Session = Depends(get_db)) -> dict:
    """更新设备"""
    device = device_service.update_device(db, device_id, data)
    return ok(data=_device_out(device), message="设备更新成功")


@router.delete("/{device_id}")
def delete_device(device_id: int, db: Session = Depends(get_db)) -> dict:
    """删除设备（有维保记录时拒绝，建议改为报废状态）"""
    device_service.delete_device(db, device_id)
    return ok(message="设备删除成功")


# ==================== 点位 ====================


@router.get("/{device_id}/points")
def list_points(device_id: int, db: Session = Depends(get_db)) -> dict:
    """设备点位列表"""
    items = device_service.list_points(db, device_id)
    return ok(data=[DevicePointOut.model_validate(p).model_dump() for p in items])


@router.post("/{device_id}/points")
def create_point(device_id: int, data: DevicePointCreate, db: Session = Depends(get_db)) -> dict:
    """新增点位（手动补充模板没有的点位类型）"""
    point = device_service.create_point(db, device_id, data)
    return ok(data=DevicePointOut.model_validate(point).model_dump(), message="点位创建成功")


@router.put("/points/{point_id}")
def update_point(point_id: int, data: DevicePointUpdate, db: Session = Depends(get_db)) -> dict:
    """更新点位（阈值/趋势参数可覆盖模板值）"""
    point = device_service.update_point(db, point_id, data)
    return ok(data=DevicePointOut.model_validate(point).model_dump(), message="点位更新成功")


@router.delete("/points/{point_id}")
def delete_point(point_id: int, db: Session = Depends(get_db)) -> dict:
    """删除点位"""
    device_service.delete_point(db, point_id)
    return ok(message="点位删除成功")
