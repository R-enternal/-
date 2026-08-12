"""用户与通知模型"""

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import IdMixin, TenantMixin, TimestampMixin


class SysUser(IdMixin, TenantMixin, TimestampMixin, Base):
    """系统用户（管理员/维修工/观察者）"""

    __tablename__ = "sys_user"

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, comment="用户名")
    password_hash: Mapped[str] = mapped_column(String(255), comment="密码哈希")
    real_name: Mapped[str | None] = mapped_column(String(50), comment="姓名")
    phone: Mapped[str | None] = mapped_column(String(20), comment="手机号")
    role: Mapped[str] = mapped_column(
        String(30),
        default="ADMIN",
        comment="角色: ADMIN/MAINTENANCE_WORKER/VIEWER",
    )
    status: Mapped[str] = mapped_column(
        String(20), default="ACTIVE", comment="状态: ACTIVE/DISABLED"
    )


class Notification(IdMixin, TenantMixin, TimestampMixin, Base):
    """站内提醒（预警/库存/工单）"""

    __tablename__ = "notification"

    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), index=True, comment="接收人")
    notify_type: Mapped[str] = mapped_column(
        String(20), index=True, comment="类型: ALERT/STOCK/WORK_ORDER"
    )
    title: Mapped[str] = mapped_column(String(200), comment="标题")
    content: Mapped[str | None] = mapped_column(Text, comment="内容")
    ref_type: Mapped[str | None] = mapped_column(String(30), comment="关联对象类型")
    ref_id: Mapped[int | None] = mapped_column(comment="关联对象ID")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, comment="已读")
