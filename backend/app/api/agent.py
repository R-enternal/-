"""Agent API：智能查询对话、维保计划、工单调度（SSE 流式）"""

import json
from collections.abc import AsyncGenerator
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.agent.aiops.service import run_plan
from app.agent.chat_agent import chat, chat_stream, clear_session, get_session_history
from app.database import get_db
from app.schemas.common import ok
from app.services import agent_service

router = APIRouter(prefix="/api/agent", tags=["智能助手"])


class ChatRequest(BaseModel):
    session_id: str = Field("default", description="会话 ID")
    question: str = Field(..., min_length=1, max_length=500, description="用户问题")


class PlanRequest(BaseModel):
    session_id: str = Field("default", description="会话 ID")
    task: str = Field("生成明天的维保计划", max_length=500, description="任务描述")


class PlanDateRequest(BaseModel):
    plan_date: str | None = Field(None, description="计划日期 YYYY-MM-DD，默认今天")
    created_by: str | None = Field("agent", description="创建人")


class ClearRequest(BaseModel):
    session_id: str = Field(..., description="会话 ID")


def _sse(generator: AsyncGenerator[dict, None]) -> EventSourceResponse:
    """包装 SSE 事件流"""

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            async for event in generator:
                yield {"event": "message", "data": json.dumps(event, ensure_ascii=False)}
                if event.get("type") in ("complete", "error"):
                    break
        except Exception as exc:  # noqa: BLE001
            yield {
                "event": "message",
                "data": json.dumps({"type": "error", "data": str(exc)}, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


@router.post("/chat_stream")
def chat_stream_endpoint(request: ChatRequest) -> EventSourceResponse:
    """流式智能查询（SSE）"""
    return _sse(chat_stream(request.question, request.session_id))


@router.post("/chat")
async def chat_endpoint(request: ChatRequest) -> dict:
    """非流式智能查询"""
    return ok(data={"answer": await chat(request.question, request.session_id)})


@router.post("/plan_stream")
def plan_stream_endpoint(request: PlanRequest) -> EventSourceResponse:
    """流式维保计划（Plan-Execute-Replan，SSE）"""
    return _sse(run_plan(request.task))


@router.get("/maintenance-plans")
def list_maintenance_plans(status: str | None = None, db: Session = Depends(get_db)) -> dict:
    """维保计划列表"""
    return ok(data=agent_service.list_plans(db, status=status))


@router.get("/maintenance-suggestions")
def maintenance_suggestions(plan_date: str | None = None, db: Session = Depends(get_db)) -> dict:
    """实时维保建议（不落库，供预览）"""
    try:
        d = date.fromisoformat(plan_date) if plan_date else None
    except ValueError as exc:
        raise ValueError("plan_date 格式应为 YYYY-MM-DD") from exc
    return ok(data=agent_service.build_maintenance_suggestions(db, d))


@router.post("/maintenance-plans/save")
def save_maintenance_plans(request: PlanDateRequest, db: Session = Depends(get_db)) -> dict:
    """把维保建议批量落库"""
    try:
        d = date.fromisoformat(request.plan_date) if request.plan_date else None
    except ValueError as exc:
        raise ValueError("plan_date 格式应为 YYYY-MM-DD") from exc
    plans = agent_service.create_plans_from_suggestions(db, d, request.created_by)
    return ok(data={"saved": len(plans)}, message=f"已保存 {len(plans)} 条维保计划")


@router.post("/maintenance-plans/{plan_id}/convert")
def convert_plan_to_order(plan_id: int, db: Session = Depends(get_db)) -> dict:
    """维保计划转工单"""
    order = agent_service.plan_to_work_order(db, plan_id)
    return ok(data=order, message=f"已生成工单：{order['order_no']}")


@router.get("/assign-suggestions")
def assign_suggestions(db: Session = Depends(get_db)) -> dict:
    """待派单工单的智能调度建议"""
    return ok(data=agent_service.assign_suggestions(db))


@router.post("/session/clear")
def clear_session_endpoint(request: ClearRequest) -> dict:
    """清空会话"""
    return ok(data={"cleared": clear_session(request.session_id)})


@router.get("/session/{session_id}/history")
def session_history(session_id: str) -> dict:
    """读取会话历史（切换页面/刷新后恢复对话）"""
    return ok(data=get_session_history(session_id))
