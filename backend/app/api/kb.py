"""知识库 API：多格式文档上传、列表、删除、语义检索"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ok
from app.services import kb_service

router = APIRouter(prefix="/api/kb", tags=["知识库"])

SUPPORTED_TYPES = {
    ".md": "MD",
    ".markdown": "MD",
    ".txt": "TXT",
    ".html": "HTML",
    ".htm": "HTML",
    ".pdf": "PDF",
    ".docx": "DOCX",
    ".json": "JSON",
    ".csv": "CSV",
    ".xlsx": "XLSX",
}


@router.post("/upload")
async def upload_document(file: UploadFile, db: Session = Depends(get_db)) -> dict:
    """上传文档并建立向量索引（支持 md/txt/html/pdf/docx/json/csv/xlsx）"""
    filename = file.filename or "unnamed"
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    doc_type = SUPPORTED_TYPES.get(suffix)
    if doc_type is None:
        raise HTTPException(
            status_code=400,
            detail="仅支持 md/txt/html/pdf/docx/json/csv/xlsx 文档",
        )

    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(status_code=400, detail="文档内容为空")
    try:
        result = kb_service.ingest_file(filename, content_bytes, created_by="admin")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(data=result, message=f"已入库 {filename}，切块 {result['chunks']} 个")


@router.post("/seed")
def seed_demo(db: Session = Depends(get_db)) -> dict:
    """灌入预置演示手册（幂等）"""
    result = kb_service.seed_demo(db)
    if not result.get("seeded"):
        return ok(data=result, message=result.get("reason", "未新增"))
    return ok(data=result, message=f"演示手册已入库，切块 {result.get('chunks', 0)} 个")


@router.get("/documents")
def list_documents(db: Session = Depends(get_db)) -> dict:
    """文档列表"""
    return ok(data=kb_service.list_documents(db))


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)) -> dict:
    """删除文档（含向量）"""
    if not kb_service.delete_document(db, doc_id):
        raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
    return ok(message="文档已删除")


@router.get("/search")
def search_kb(q: str, k: int = 4) -> dict:
    """语义检索（调试/预览用）"""
    return ok(data=kb_service.search(q, k=k))
