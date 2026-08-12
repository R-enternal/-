"""ORM 模型包：统一导出，供 Alembic 自动迁移和业务代码引用"""

from app.models.agent import MaintenanceBusyWindow, MaintenancePlan
from app.models.device import Device, DevicePoint, DeviceTypeThreshold, MaintenanceRecord
from app.models.fusion import FusionDiagnosis
from app.models.kb import KbDocument
from app.models.monitor import Alert, HealthRecord, SensorData
from app.models.spare_part import SparePart, StockRecord
from app.models.user import Notification, SysUser
from app.models.warehouse import Warehouse
from app.models.work_order import WorkOrder, WorkOrderPart

__all__ = [
    "Warehouse",
    "Device",
    "DevicePoint",
    "DeviceTypeThreshold",
    "MaintenanceRecord",
    "SensorData",
    "HealthRecord",
    "Alert",
    "WorkOrder",
    "WorkOrderPart",
    "SparePart",
    "StockRecord",
    "SysUser",
    "Notification",
    "MaintenanceBusyWindow",
    "MaintenancePlan",
    "KbDocument",
    "FusionDiagnosis",
]
