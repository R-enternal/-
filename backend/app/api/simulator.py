"""模拟数据源接口"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ok
from app.services import sensor_service

router = APIRouter(prefix="/api/simulator", tags=["模拟数据"])


class SimulatorRunRequest(BaseModel):
    minutes: int = Field(120, ge=1, le=1440, description="生成最近多少分钟的数据")
    seed: int | None = Field(None, description="随机种子（测试可复现）")


@router.post("/run")
def run_simulator(data: SimulatorRunRequest, db: Session = Depends(get_db)) -> dict:
    """手动触发一轮模拟数据生成（写入 sensor_data）"""
    result = sensor_service.generate_history(db, minutes=data.minutes, seed=data.seed)
    message = (
        f"已为 {result['points']} 个点位生成 {result['rows']} 条数据"
        if result["rows"]
        else "没有启用的点位，未生成数据"
    )
    return ok(data=result, message=message)
