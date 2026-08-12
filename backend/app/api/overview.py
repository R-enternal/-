"""看板总览路由"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ok
from app.services import overview_service

router = APIRouter(prefix="/api/overview", tags=["看板"])


@router.get("/stats")
def overview_stats(db: Session = Depends(get_db)) -> dict:
    """首页 KPI 总览（设备/健康度/告警/工单/备件一次返回）"""
    return ok(data=overview_service.get_overview_stats(db))
