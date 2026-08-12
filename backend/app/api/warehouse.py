"""仓库路由"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ok
from app.schemas.warehouse import WarehouseCreate, WarehouseOut, WarehouseUpdate
from app.services import device_service

router = APIRouter(prefix="/api/warehouses", tags=["仓库"])


@router.get("")
def list_warehouses(db: Session = Depends(get_db)) -> dict:
    """仓库列表"""
    items = device_service.list_warehouses(db)
    return ok(data=[WarehouseOut.model_validate(w).model_dump() for w in items])


@router.get("/{warehouse_id}")
def get_warehouse(warehouse_id: int, db: Session = Depends(get_db)) -> dict:
    """仓库详情"""
    wh = device_service.get_warehouse(db, warehouse_id)
    return ok(data=WarehouseOut.model_validate(wh).model_dump())


@router.post("")
def create_warehouse(data: WarehouseCreate, db: Session = Depends(get_db)) -> dict:
    """新建仓库"""
    wh = device_service.create_warehouse(db, data)
    return ok(data=WarehouseOut.model_validate(wh).model_dump(), message="仓库创建成功")


@router.put("/{warehouse_id}")
def update_warehouse(
    warehouse_id: int, data: WarehouseUpdate, db: Session = Depends(get_db)
) -> dict:
    """更新仓库"""
    wh = device_service.update_warehouse(db, warehouse_id, data)
    return ok(data=WarehouseOut.model_validate(wh).model_dump(), message="仓库更新成功")


@router.delete("/{warehouse_id}")
def delete_warehouse(warehouse_id: int, db: Session = Depends(get_db)) -> dict:
    """删除仓库（仓库下有设备时拒绝）"""
    device_service.delete_warehouse(db, warehouse_id)
    return ok(message="仓库删除成功")
