"""知识库模型：上传文档记录（向量本体在 Chroma）"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import IdMixin, TenantMixin, TimestampMixin


class KbDocument(IdMixin, TenantMixin, TimestampMixin, Base):
    """知识库文档（上传记录，向量数据持久化在 Chroma）"""

    __tablename__ = "kb_document"

    filename: Mapped[str] = mapped_column(String(255), index=True, comment="原始文件名")
    doc_type: Mapped[str] = mapped_column(String(20), default="MD", comment="文档类型: MD/TXT")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, comment="切块数量")
    status: Mapped[str] = mapped_column(
        String(20), default="READY", comment="状态: READY/FAILED"
    )
    created_by: Mapped[str | None] = mapped_column(String(50), comment="上传人")
