"""仓库模型"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import IdMixin, TenantMixin, TimestampMixin


class Warehouse(IdMixin, TenantMixin, TimestampMixin, Base):
    """仓库（SaaS 多租户预留，MVP 单仓也保留）"""

    __tablename__ = "warehouse"

    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="仓库名称")
    address: Mapped[str | None] = mapped_column(String(255), comment="仓库地址")
    contact_name: Mapped[str | None] = mapped_column(String(50), comment="联系人")
    contact_phone: Mapped[str | None] = mapped_column(String(20), comment="联系电话")
    status: Mapped[str] = mapped_column(
        String(20), default="ACTIVE", comment="状态: ACTIVE/DISABLED"
    )
