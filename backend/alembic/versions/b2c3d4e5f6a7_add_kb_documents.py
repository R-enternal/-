"""add kb_documents

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-05 02:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kb_document",
        sa.Column("filename", sa.String(length=255), nullable=False, comment="原始文件名"),
        sa.Column("doc_type", sa.String(length=20), nullable=False, comment="文档类型"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, comment="切块数量"),
        sa.Column("status", sa.String(length=20), nullable=False, comment="状态"),
        sa.Column("created_by", sa.String(length=50), nullable=True, comment="上传人"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, comment="租户ID（预留）"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_document_filename", "kb_document", ["filename"], unique=False)
    op.create_index("ix_kb_document_tenant_id", "kb_document", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_kb_document_tenant_id", table_name="kb_document")
    op.drop_index("ix_kb_document_filename", table_name="kb_document")
    op.drop_table("kb_document")
