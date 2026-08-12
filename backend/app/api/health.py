"""健康度路由"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ok
from app.services import health_service

router = APIRouter(prefix="/api/health", tags=["健康度"])


@router.post("/compute")
def compute_health(db: Session = Depends(get_db)) -> dict:
    """手动触发一次健康度计算（写入 health_record）"""
    result = health_service.compute_all_health(db)
    message = f"计算 {result['devices']} 台设备，写入 {result['records']} 条健康度记录"
    return ok(data=result, message=message)


@router.get("")
def list_health(
    device_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> dict:
    """健康度记录列表（按时间倒序，趋势图数据源）"""
    items = health_service.list_health_records(db, device_id=device_id, limit=limit)
    return ok(data=items)
