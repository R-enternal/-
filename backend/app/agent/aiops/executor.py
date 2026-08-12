"""Executor 节点：执行单个步骤（调用工具收集数据）"""

from typing import Any

from loguru import logger

from app.agent.aiops.state import PlanState
from app.tools import (
    get_busy_window,
    query_alerts,
    query_device_health,
    query_spare_parts,
)


async def executor(state: PlanState) -> dict[str, Any]:
    """执行计划中的下一个步骤：按步骤关键词路由到工具"""
    plan = state.get("plan", [])
    if not plan:
        return {}
    task = plan[0]
    logger.info(f"[维保Agent] Executor 执行: {task}")

    # 步骤 → 工具路由
    if "健康度" in task or "健康" in task:
        result = await query_device_health.ainvoke({})
    elif "告警" in task:
        result = await query_alerts.ainvoke({"status": "PENDING"})
    elif "备件" in task or "库存" in task:
        result = await query_spare_parts.ainvoke({"low_stock_only": False})
    elif "忙" in task or "闲" in task:
        result = await get_busy_window.ainvoke({"weekday": None})
    else:
        result = "（该步骤无需查询，跳过）"

    return {"plan": plan[1:], "past_steps": [(task, str(result))], "step_count": state["step_count"] + 1}
