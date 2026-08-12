"""仓库请求/响应模型"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WarehouseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="仓库名称")
    address: str | None = Field(None, max_length=255, description="仓库地址")
    contact_name: str | None = Field(None, max_length=50, description="联系人")
    contact_phone: str | None = Field(None, max_length=20, description="联系电话")


class WarehouseCreate(WarehouseBase):
    """新建仓库"""


class WarehouseUpdate(BaseModel):
    """更新仓库（全字段可选）"""

    name: str | None = Field(None, min_length=1, max_length=100)
    address: str | None = Field(None, max_length=255)
    contact_name: str | None = Field(None, max_length=50)
    contact_phone: str | None = Field(None, max_length=20)
    status: str | None = Field(None, description="ACTIVE/DISABLED")


class WarehouseOut(WarehouseBase):
    """仓库响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    created_at: datetime
