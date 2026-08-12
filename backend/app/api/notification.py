"""通知中心路由"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import SysUser
from app.schemas.common import ok
from app.services import auth_service, notification_service

router = APIRouter(prefix="/api/notifications", tags=["通知"])


class MarkReadRequest(BaseModel):
    notification_id: int | None = Field(None, description="指定通知ID，不传则全部已读")


def _effective_user_id(
    db: Session,
    user_id: int | None,
    current_user: SysUser | None,
) -> int:
    """确定接收人：认证开启用 token 用户；联调期用参数，缺省取第一个 ADMIN"""
    if current_user is not None:
        return current_user.id
    if user_id is not None:
        return user_id
    first_admin = db.scalar(
        select(SysUser.id)
        .where(SysUser.role == "ADMIN", SysUser.status == "ACTIVE")
        .order_by(SysUser.id)
        .limit(1)
    )
    return first_admin or 0


@router.get("")
def list_notifications(
    user_id: int | None = None,
    is_read: bool | None = None,
    current_user: SysUser | None = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """通知列表（按时间倒序，可按已读/未读过滤）"""
    uid = _effective_user_id(db, user_id, current_user)
    items = notification_service.list_notifications(db, uid, is_read=is_read)
    return ok(
        data=[
            {
                "id": n.id,
                "notify_type": n.notify_type,
                "title": n.title,
                "content": n.content,
                "ref_type": n.ref_type,
                "ref_id": n.ref_id,
                "is_read": n.is_read,
                "created_at": n.created_at,
            }
            for n in items
        ]
    )


@router.get("/unread-count")
def unread_count(
    user_id: int | None = None,
    current_user: SysUser | None = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """未读通知数"""
    uid = _effective_user_id(db, user_id, current_user)
    return ok(data={"user_id": uid, "unread": notification_service.unread_count(db, uid)})


@router.post("/read")
def mark_read(
    data: MarkReadRequest,
    user_id: int | None = None,
    current_user: SysUser | None = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """标记已读（指定单条或全部）"""
    uid = _effective_user_id(db, user_id, current_user)
    count = notification_service.mark_read(db, uid, data.notification_id)
    return ok(data={"marked": count}, message=f"已标记 {count} 条已读")
