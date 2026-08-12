"""融合诊断 API"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ok
from app.services import device_service, fusion_service

router = APIRouter(prefix="/api/diagnosis", tags=["融合诊断"])


@router.get("/{device_id}")
def diagnose_device(device_id: int, db: Session = Depends(get_db)) -> dict:
    """对单台设备做实时融合诊断（振动+温度+电流联合判定）"""
    device_service.get_device(db, device_id)  # 404 兜底
    return ok(data=fusion_service.diagnose_device(db, device_id))


@router.get("")
def list_diagnoses(
    device_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> dict:
    """最近诊断记录列表"""
    return ok(data=fusion_service.latest_diagnoses(db, device_id=device_id, limit=limit))


@router.post("/run")
def run_diagnoses(db: Session = Depends(get_db)) -> dict:
    """对全部运行设备批量诊断"""
    result = fusion_service.diagnose_all(db)
    return ok(data=result, message=f"已诊断 {result['devices']} 台设备")
