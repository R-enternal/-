"""备件服务：CRUD、入库/出库（同事务 + 流水）、库存查询"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.spare_part import SparePart, StockRecord
from app.models.warehouse import Warehouse
from app.schemas.spare_part import SparePartCreate, SparePartUpdate, StockChangeRequest
from app.services import notification_service


def create_spare_part(db: Session, data: SparePartCreate) -> SparePart:
    """新建备件（part_code 唯一）"""
    if db.get(Warehouse, data.warehouse_id) is None:
        raise HTTPException(status_code=404, detail=f"仓库不存在: {data.warehouse_id}")
    exists = db.scalar(select(SparePart.id).where(SparePart.part_code == data.part_code).limit(1))
    if exists is not None:
        raise HTTPException(status_code=400, detail=f"备件编号已存在: {data.part_code}")

    part = SparePart(**data.model_dump())
    db.add(part)
    db.commit()
    db.refresh(part)
    return part


def get_spare_part(db: Session, part_id: int) -> SparePart:
    part = db.get(SparePart, part_id)
    if part is None:
        raise HTTPException(status_code=404, detail=f"备件不存在: {part_id}")
    return part


def update_spare_part(db: Session, part_id: int, data: SparePartUpdate) -> SparePart:
    part = get_spare_part(db, part_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(part, key, value)
    db.commit()
    db.refresh(part)
    return part


def delete_spare_part(db: Session, part_id: int) -> None:
    """删除备件（有库存流水时拒绝，避免历史记录悬空）"""
    part = get_spare_part(db, part_id)
    has_record = db.scalar(
        select(StockRecord.id).where(StockRecord.spare_part_id == part_id).limit(1)
    )
    if has_record is not None:
        raise HTTPException(
            status_code=400,
            detail=f"备件存在库存流水，无法删除（可改为 DISABLED 状态）: {part_id}",
        )
    db.delete(part)
    db.commit()


def list_spare_parts(
    db: Session,
    warehouse_id: int | None = None,
    low_stock: bool = False,
) -> list[SparePart]:
    """备件列表（支持按仓库过滤、低库存筛选）"""
    stmt = select(SparePart).order_by(SparePart.id)
    if warehouse_id is not None:
        stmt = stmt.where(SparePart.warehouse_id == warehouse_id)
    if low_stock:
        stmt = stmt.where(SparePart.stock_quantity < SparePart.safe_quantity)
    return list(db.scalars(stmt))


def change_stock(
    db: Session,
    part_id: int,
    data: StockChangeRequest,
    change_type: str,
) -> SparePart:
    """入库/出库：库存增减与流水在同一事务提交

    - INBOUND：库存增加 +quantity
    - OUTBOUND：库存减少 -quantity，不足时 400（无任何变更，天然回滚）
    """
    part = get_spare_part(db, part_id)
    delta = data.quantity if change_type == "INBOUND" else -data.quantity

    if change_type == "OUTBOUND" and part.stock_quantity < data.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"库存不足：当前 {part.stock_quantity}，出库 {data.quantity}",
        )

    # 穿越安全线判定：变动前 >= 安全线 且 变动后 < 安全线，才发一次通知（避免刷屏）
    crossed_below = (
        part.safe_quantity > 0
        and part.stock_quantity >= part.safe_quantity
        and part.stock_quantity + delta < part.safe_quantity
    )
    part.stock_quantity += delta
    db.add(
        StockRecord(
            spare_part_id=part.id,
            change_type=change_type,
            quantity=delta,
            balance_after=part.stock_quantity,
            operator=data.operator,
            remark=data.remark,
        )
    )
    # 通知：穿越安全线（由充足变为不足）→ 发给所有 ADMIN
    if crossed_below:
        notification_service.notify(
            db,
            notify_type="STOCK",
            title=f"备件低库存预警：{part.name}",
            content=(f"当前库存 {part.stock_quantity}，安全库存 {part.safe_quantity}"),
            ref_type="SPARE_PART",
            ref_id=part.id,
        )
    db.commit()
    db.refresh(part)
    return part


def list_stock_records(db: Session, part_id: int) -> list[StockRecord]:
    """备件库存流水（按时间倒序）"""
    get_spare_part(db, part_id)
    return list(
        db.scalars(
            select(StockRecord)
            .where(StockRecord.spare_part_id == part_id)
            .order_by(StockRecord.created_at.desc(), StockRecord.id.desc())
        )
    )
