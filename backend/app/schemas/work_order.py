"""工单请求/响应模型"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkOrderCreate(BaseModel):
    """创建工单"""

    warehouse_id: int = Field(..., description="仓库ID")
    device_id: int = Field(..., description="设备ID")
    title: str = Field(..., min_length=1, max_length=200, description="工单标题")
    description: str | None = Field(None, max_length=2000, description="问题描述")
    order_type: str = Field("MAINTENANCE", description="类型: REPAIR/MAINTENANCE/INSPECTION/OTHER")
    priority: str = Field("MEDIUM", description="优先级: LOW/MEDIUM/HIGH/URGENT")
    source: str = Field("MANUAL", description="来源: ALERT/PLAN/MANUAL")


TransitionAction = Literal["assign", "start", "submit", "complete", "cancel"]


class WorkOrderTransition(BaseModel):
    """工单状态流转"""

    action: TransitionAction = Field(..., description="流转动作")
    assignee_id: int | None = Field(None, description="指派人（assign 动作使用）")
    result: str | None = Field(None, max_length=2000, description="处理结果（complete 使用）")


class WorkOrderPartAdd(BaseModel):
    """登记工单使用备件"""

    spare_part_id: int = Field(..., description="备件ID")
    quantity: int = Field(..., gt=0, description="数量")


class WorkOrderPartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int
    spare_part_id: int
    quantity: int
    unit_price: Decimal | None
    created_at: datetime


class WorkOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_no: str
    warehouse_id: int
    device_id: int
    title: str
    description: str | None
    order_type: str
    priority: str
    source: str
    alert_id: int | None
    assignee_id: int | None
    status: str
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    result: str | None
    created_at: datetime
