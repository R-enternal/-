"""模型公共基类与工具"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column


class IdMixin:
    """主键"""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="主键")


class TimestampMixin:
    """创建/更新时间"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )


class TenantMixin:
    """多租户预留字段（企划书 SaaS 承诺）"""

    tenant_id: Mapped[str] = mapped_column(
        String(64), default="default", index=True, comment="租户ID（预留）"
    )
