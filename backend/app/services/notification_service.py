"""通知中心服务：创建通知、列表、已读管理

通知产生逻辑在对应业务 service 里调用本服务的 notify()，
本服务只负责"发给谁 + 写表 + 查询"。
"""

from typing import cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.orm import Session

from app.models.user import Notification, SysUser


def _admin_user_ids(db: Session) -> list[int]:
    """所有 ADMIN 用户（通知的默认接收人）"""
    return list(
        db.scalars(select(SysUser.id).where(SysUser.role == "ADMIN", SysUser.status == "ACTIVE"))
    )


def notify(
    db: Session,
    *,
    notify_type: str,
    title: str,
    content: str | None = None,
    ref_type: str | None = None,
    ref_id: int | None = None,
    extra_user_ids: list[int] | None = None,
) -> int:
    """创建通知：发给所有 ADMIN + 额外用户（如工单指派人）

    Returns: 创建的通知条数
    """
    receiver_ids = set(_admin_user_ids(db))
    if extra_user_ids:
        receiver_ids.update(extra_user_ids)
    if not receiver_ids:
        return 0

    for uid in receiver_ids:
        db.add(
            Notification(
                user_id=uid,
                notify_type=notify_type,
                title=title,
                content=content,
                ref_type=ref_type,
                ref_id=ref_id,
            )
        )
    return len(receiver_ids)


def list_notifications(
    db: Session,
    user_id: int,
    is_read: bool | None = None,
) -> list[Notification]:
    """通知列表（按时间倒序，可按已读/未读过滤）"""
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    )
    if is_read is not None:
        stmt = stmt.where(Notification.is_read == is_read)
    return list(db.scalars(stmt))


def unread_count(db: Session, user_id: int) -> int:
    """未读通知数"""
    return int(
        db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        )
        or 0
    )


def mark_read(db: Session, user_id: int, notification_id: int | None = None) -> int:
    """标记已读：指定 id 单条，或全部（notification_id=None）"""
    stmt = update(Notification).where(
        Notification.user_id == user_id,
        Notification.is_read.is_(False),
    )
    if notification_id is not None:
        stmt = stmt.where(Notification.id == notification_id)
    result = cast(CursorResult, db.execute(stmt.values(is_read=True)))
    db.commit()
    return result.rowcount or 0
