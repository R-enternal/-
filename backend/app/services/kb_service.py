"""知识库服务：文档上传 → 切块 → 向量化（智谱 embedding）→ Chroma 检索"""

from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import config
from app.database import SessionLocal
from app.models.kb import KbDocument

_COLLECTION = "kb_docs"
_vector_store: Chroma | None = None


def _get_embeddings() -> OpenAIEmbeddings:
    """智谱 GLM embedding（OpenAI 兼容）"""
    return OpenAIEmbeddings(
        model=config.embedding_model,
        api_key=SecretStr(config.embedding_api_key),
        base_url=config.embedding_base_url,
    )


def _get_vector_store() -> Chroma:
    """Chroma 持久化向量库（单例级：模块内缓存）"""
    global _vector_store
    if _vector_store is None:
        Path(config.kb_vector_dir).mkdir(parents=True, exist_ok=True)
        _vector_store = Chroma(
            collection_name=_COLLECTION,
            embedding_function=_get_embeddings(),
            persist_directory=config.kb_vector_dir,
        )
    return _vector_store


def _split_text(content: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.kb_chunk_size,
        chunk_overlap=config.kb_chunk_overlap,
    )
    return splitter.split_text(content)


def ingest_text(filename: str, content: str, doc_type: str = "MD", created_by: str | None = "admin") -> dict[str, Any]:
    """把一个文档切块、向量化并写入 Chroma，同时记录 KbDocument"""
    chunks = _split_text(content)
    if not chunks:
        return {"chunks": 0}

    docs = [
        Document(page_content=chunk, metadata={"source": filename, "chunk_index": i})
        for i, chunk in enumerate(chunks)
    ]
    store = _get_vector_store()
    store.add_documents(docs)
    logger.info(f"[知识库] 已入库 {filename}: {len(chunks)} 块")

    db = SessionLocal()
    try:
        record = KbDocument(
            filename=filename,
            doc_type=doc_type,
            chunk_count=len(chunks),
            status="READY",
            created_by=created_by,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        doc_id = record.id
    finally:
        db.close()
    return {"doc_id": doc_id, "chunks": len(chunks)}


def search(query: str, k: int | None = None) -> list[dict[str, Any]]:
    """语义检索：返回 top-k 片段（带来源与相似度）"""
    store = _get_vector_store()
    results = store.similarity_search_with_relevance_scores(
        query, k=k or config.kb_top_k
    )
    items = []
    for doc, score in results:
        items.append(
            {
                "content": doc.page_content,
                "source": doc.metadata.get("source", "未知来源"),
                "score": round(float(score), 4),
            }
        )
    return items


def search_as_context(query: str, k: int | None = None) -> str:
    """检索并格式化为 LLM 友好的上下文文本"""
    items = search(query, k)
    if not items:
        return "没有找到相关资料。"
    parts = []
    for i, item in enumerate(items, 1):
        parts.append(f"【资料 {i} | 来源: {item['source']}】\n{item['content']}")
    return "\n\n".join(parts)


def list_documents(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(KbDocument).order_by(KbDocument.created_at.desc())
    ).all()
    return [
        {
            "id": row.id,
            "filename": row.filename,
            "doc_type": row.doc_type,
            "chunk_count": row.chunk_count,
            "status": row.status,
            "created_by": row.created_by,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def delete_document(db: Session, doc_id: int) -> bool:
    """删除文档：清 Chroma 中该来源向量 + 删记录"""
    record = db.get(KbDocument, doc_id)
    if record is None:
        return False
    store = _get_vector_store()
    try:
        store.delete(where={"source": record.filename})
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[知识库] 删除向量失败（可能已不存在）: {exc}")
    db.delete(record)
    db.commit()
    return True


def seed_demo(db: Session) -> dict[str, Any]:
    """灌入预置演示手册（已存在则跳过）"""
    from pathlib import Path

    doc_path = Path(__file__).resolve().parents[2] / "kb_docs" / "设备维保手册.md"
    if not doc_path.exists():
        return {"seeded": False, "reason": "演示手册文件不存在"}
    exists = db.scalar(select(KbDocument.id).where(KbDocument.filename == doc_path.name).limit(1))
    if exists is not None:
        return {"seeded": False, "reason": "演示手册已存在"}
    result = ingest_text(doc_path.name, doc_path.read_text(encoding="utf-8"), doc_type="MD", created_by="seed")
    return {"seeded": True, **result}
