"""备件请求/响应模型"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SparePartCreate(BaseModel):
    """新建备件"""

    warehouse_id: int = Field(..., description="所属仓库")
    part_code: str = Field(..., min_length=1, max_length=50, description="备件编号")
    name: str = Field(..., min_length=1, max_length=100, description="备件名称")
    spec: str | None = Field(None, max_length=100, description="规格型号")
    unit: str | None = Field("个", max_length=20, description="单位")
    stock_quantity: int = Field(0, ge=0, description="初始库存")
    safe_quantity: int = Field(0, ge=0, description="安全库存")
    storage_location: str | None = Field(None, max_length=50, description="库位")
    supplier: str | None = Field(None, max_length=100, description="供应商")
    price: Decimal | None = Field(None, description="参考单价")


class SparePartUpdate(BaseModel):
    """更新备件（全字段可选）"""

    name: str | None = Field(None, min_length=1, max_length=100)
    spec: str | None = Field(None, max_length=100)
    unit: str | None = Field(None, max_length=20)
    safe_quantity: int | None = Field(None, ge=0)
    storage_location: str | None = Field(None, max_length=50)
    supplier: str | None = Field(None, max_length=100)
    price: Decimal | None = None
    status: str | None = Field(None, description="ACTIVE/DISABLED")


class StockChangeRequest(BaseModel):
    """入库/出库请求"""

    quantity: int = Field(..., gt=0, description="变动数量（正数）")
    operator: str | None = Field(None, max_length=50, description="操作人")
    remark: str | None = Field(None, max_length=500, description="备注")


class SparePartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    warehouse_id: int
    part_code: str
    name: str
    spec: str | None
    unit: str | None
    stock_quantity: int
    safe_quantity: int
    storage_location: str | None
    supplier: str | None
    price: Decimal | None
    status: str
    created_at: datetime


class StockRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    spare_part_id: int
    change_type: str
    quantity: int
    balance_after: int
    related_work_order_id: int | None
    operator: str | None
    remark: str | None
    created_at: datetime
