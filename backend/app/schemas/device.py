"""设备与点位请求/响应模型"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 设备类型枚举：Pydantic 校验失败自动返回 422，防止手滑传小写/拼错
DeviceType = Literal["CONVEYOR", "STACKER", "AGV", "SORTER", "FORKLIFT"]


class DevicePointBase(BaseModel):
    point_code: str = Field(..., min_length=1, max_length=50, description="点位编号")
    point_type: str = Field(..., description="点位类型: VIBRATION/TEMPERATURE/CURRENT")
    unit: str | None = Field(None, max_length=20, description="单位")
    alarm_low: float | None = Field(None, description="报警下限")
    alarm_high: float | None = Field(None, description="报警上限")
    trend_window: int | None = Field(None, ge=5, le=1440, description="趋势窗口（采样点数）")
    trend_delta: float | None = Field(None, description="趋势上升幅度阈值")
    collect_interval_seconds: int | None = Field(None, ge=5, le=3600, description="采集频率（秒）")


class DevicePointCreate(DevicePointBase):
    """新建点位"""


class DevicePointUpdate(BaseModel):
    """更新点位（全字段可选）"""

    point_code: str | None = Field(None, min_length=1, max_length=50)
    unit: str | None = Field(None, max_length=20)
    alarm_low: float | None = None
    alarm_high: float | None = None
    trend_window: int | None = Field(None, ge=5, le=1440)
    trend_delta: float | None = None
    collect_interval_seconds: int | None = Field(None, ge=5, le=3600)
    enabled: bool | None = None


class DevicePointOut(DevicePointBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    trend_window: int
    trend_delta: float
    collect_interval_seconds: int
    enabled: bool
    created_at: datetime


class DeviceCreate(BaseModel):
    warehouse_id: int = Field(..., description="所属仓库ID")
    device_code: str = Field(..., min_length=1, max_length=50, description="设备编号")
    name: str = Field(..., min_length=1, max_length=100, description="设备名称")
    device_type: DeviceType
    brand: str | None = Field(None, max_length=50)
    model: str | None = Field(None, max_length=50)
    location: str | None = Field(None, max_length=100, description="安装位置")
    purchase_date: date | None = None
    install_date: date | None = None
    lifespan_years: int | None = Field(None, ge=1, le=50)
    supplier: str | None = Field(None, max_length=100)
    price: Decimal | None = Field(None, description="采购价格")
    description: str | None = None
    auto_create_points: bool = Field(True, description="是否按设备类型模板自动创建传感器点位")


class DeviceUpdate(BaseModel):
    """更新设备（全字段可选）"""

    warehouse_id: int | None = None
    device_code: str | None = Field(None, min_length=1, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=100)
    device_type: DeviceType | None = None
    brand: str | None = Field(None, max_length=50)
    model: str | None = Field(None, max_length=50)
    location: str | None = Field(None, max_length=100)
    status: str | None = Field(None, description="RUNNING/STOPPED/MAINTENANCE/SCRAPPED")
    purchase_date: date | None = None
    install_date: date | None = None
    scrap_date: date | None = None
    lifespan_years: int | None = Field(None, ge=1, le=50)
    supplier: str | None = Field(None, max_length=100)
    price: Decimal | None = None
    description: str | None = None


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    warehouse_id: int
    device_code: str
    name: str
    device_type: str
    brand: str | None
    model: str | None
    location: str | None
    status: str
    purchase_date: date | None
    install_date: date | None
    scrap_date: date | None
    lifespan_years: int | None
    supplier: str | None
    price: Decimal | None
    description: str | None
    created_at: datetime


class DeviceWithPointsOut(DeviceOut):
    """设备详情（含点位列表）"""

    points: list[DevicePointOut] = []
