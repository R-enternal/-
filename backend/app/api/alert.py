"""告警路由"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ok
from app.services import alert_service, work_order_service

router = APIRouter(prefix="/api/alerts", tags=["告警"])


class AlertHandleRequest(BaseModel):
    """告警处理请求（确认/忽略共用）

    handled_by 在认证模块落地前由请求方传入，之后改为从 token 注入
    """

    handled_by: str | None = Field(None, max_length=50, description="处理人")
    handle_note: str | None = Field(None, max_length=500, description="处理说明")


@router.get("")
def list_alerts(
    device_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """告警列表（支持按设备/状态过滤）"""
    items = alert_service.list_alerts_with_context(db, device_id=device_id, status=status)
    return ok(data=items)


@router.get("/{alert_id}")
def get_alert(alert_id: int, db: Session = Depends(get_db)) -> dict:
    """告警详情（含设备/点位上下文）"""
    data = alert_service.get_alert_with_context(db, alert_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"告警不存在: {alert_id}")
    return ok(data=data)


@router.post("/check")
def check_alerts(db: Session = Depends(get_db)) -> dict:
    """手动触发一次阈值判定（对全部启用点位）"""
    result = alert_service.check_all_points(db)
    message = f"检查 {result['points']} 个点位，新增 {result['created']} 条告警"
    return ok(data=result, message=message)


@router.post("/{alert_id}/handle")
def handle_alert(alert_id: int, data: AlertHandleRequest, db: Session = Depends(get_db)) -> dict:
    """确认告警：PENDING → HANDLED（重复处理返回 400）"""
    alert = alert_service.handle_alert(
        db, alert_id, handled_by=data.handled_by, handle_note=data.handle_note
    )
    return ok(
        data=alert_service.get_alert_with_context(db, alert.id),
        message="告警已确认",
    )


@router.post("/{alert_id}/ignore")
def ignore_alert(alert_id: int, data: AlertHandleRequest, db: Session = Depends(get_db)) -> dict:
    """忽略告警：PENDING → IGNORED（重复处理返回 400）"""
    alert = alert_service.ignore_alert(
        db, alert_id, handled_by=data.handled_by, handle_note=data.handle_note
    )
    return ok(
        data=alert_service.get_alert_with_context(db, alert.id),
        message="告警已忽略",
    )


@router.post("/{alert_id}/convert")
def convert_alert(alert_id: int, db: Session = Depends(get_db)) -> dict:
    """告警转工单：仅 HANDLED 可转，转后告警变 CONVERTED"""
    order = work_order_service.create_from_alert(db, alert_id)
    return ok(
        data=work_order_service.work_order_with_names(db, order),
        message=f"已生成工单：{order.order_no}",
    )
