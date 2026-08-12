"""备件域模型：备件库存 + 库存流水"""

from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import IdMixin, TenantMixin, TimestampMixin


class SparePart(IdMixin, TenantMixin, TimestampMixin, Base):
    """备件库存"""

    __tablename__ = "spare_part"

    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse.id"), index=True, comment="仓库"
    )
    part_code: Mapped[str] = mapped_column(String(50), unique=True, comment="备件编号")
    name: Mapped[str] = mapped_column(String(100), comment="备件名称")
    spec: Mapped[str | None] = mapped_column(String(100), comment="规格型号")
    unit: Mapped[str | None] = mapped_column(String(20), default="个", comment="单位")
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, comment="当前库存")
    safe_quantity: Mapped[int] = mapped_column(Integer, default=0, comment="安全库存")
    storage_location: Mapped[str | None] = mapped_column(String(50), comment="库位")
    supplier: Mapped[str | None] = mapped_column(String(100), comment="供应商")
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), comment="参考单价")
    status: Mapped[str] = mapped_column(
        String(20), default="ACTIVE", comment="状态: ACTIVE/DISABLED"
    )


class StockRecord(IdMixin, TenantMixin, TimestampMixin, Base):
    """库存流水（入库/出库/工单消耗/盘点/报损）"""

    __tablename__ = "stock_record"

    spare_part_id: Mapped[int] = mapped_column(
        ForeignKey("spare_part.id"), index=True, comment="备件"
    )
    change_type: Mapped[str] = mapped_column(
        String(20), comment="类型: INBOUND/OUTBOUND/WORK_ORDER/INVENTORY/LOSS"
    )
    quantity: Mapped[int] = mapped_column(Integer, comment="变动数量（正负）")
    balance_after: Mapped[int] = mapped_column(Integer, comment="变动后余量")
    related_work_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("work_order.id"), comment="关联工单"
    )
    operator: Mapped[str | None] = mapped_column(String(50), comment="操作人")
    remark: Mapped[str | None] = mapped_column(Text, comment="备注")
