"""备件路由"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ok
from app.schemas.spare_part import (
    SparePartCreate,
    SparePartOut,
    SparePartUpdate,
    StockChangeRequest,
    StockRecordOut,
)
from app.services import spare_part_service

router = APIRouter(prefix="/api/spare-parts", tags=["备件"])


@router.post("")
def create_spare_part(data: SparePartCreate, db: Session = Depends(get_db)) -> dict:
    """新建备件"""
    part = spare_part_service.create_spare_part(db, data)
    return ok(data=SparePartOut.model_validate(part).model_dump(), message="备件创建成功")


@router.get("")
def list_spare_parts(
    warehouse_id: int | None = None,
    low_stock: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    """备件列表（支持按仓库过滤、低库存筛选）"""
    parts = spare_part_service.list_spare_parts(db, warehouse_id, low_stock)
    return ok(data=[SparePartOut.model_validate(p).model_dump() for p in parts])


@router.get("/{part_id}")
def get_spare_part(part_id: int, db: Session = Depends(get_db)) -> dict:
    """备件详情"""
    part = spare_part_service.get_spare_part(db, part_id)
    return ok(data=SparePartOut.model_validate(part).model_dump())


@router.put("/{part_id}")
def update_spare_part(part_id: int, data: SparePartUpdate, db: Session = Depends(get_db)) -> dict:
    """更新备件"""
    part = spare_part_service.update_spare_part(db, part_id, data)
    return ok(data=SparePartOut.model_validate(part).model_dump(), message="备件更新成功")


@router.delete("/{part_id}")
def delete_spare_part(part_id: int, db: Session = Depends(get_db)) -> dict:
    """删除备件（有流水记录时拒绝）"""
    spare_part_service.delete_spare_part(db, part_id)
    return ok(message="备件删除成功")


@router.post("/{part_id}/inbound")
def inbound(part_id: int, data: StockChangeRequest, db: Session = Depends(get_db)) -> dict:
    """入库（库存与流水同事务）"""
    part = spare_part_service.change_stock(db, part_id, data, "INBOUND")
    return ok(
        data=SparePartOut.model_validate(part).model_dump(),
        message=f"入库成功，当前库存 {part.stock_quantity}",
    )


@router.post("/{part_id}/outbound")
def outbound(part_id: int, data: StockChangeRequest, db: Session = Depends(get_db)) -> dict:
    """出库（库存不足返回 400）"""
    part = spare_part_service.change_stock(db, part_id, data, "OUTBOUND")
    return ok(
        data=SparePartOut.model_validate(part).model_dump(),
        message=f"出库成功，当前库存 {part.stock_quantity}",
    )


@router.get("/{part_id}/records")
def list_records(part_id: int, db: Session = Depends(get_db)) -> dict:
    """备件库存流水"""
    records = spare_part_service.list_stock_records(db, part_id)
    return ok(data=[StockRecordOut.model_validate(r).model_dump() for r in records])
