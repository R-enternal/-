"""Replanner 节点：决定继续执行还是生成最终报告"""

from typing import Any

from loguru import logger

from app.agent.aiops.state import PlanState
from app.config import config


async def replanner(state: PlanState) -> dict[str, Any]:
    """剩余计划为空、或步数超限时生成报告；否则继续执行"""
    if state.get("plan") or state.get("step_count", 0) >= config.agent_max_steps:
        if state.get("step_count", 0) >= config.agent_max_steps and state.get("plan"):
            logger.warning("[维保Agent] 达到步数上限，提前生成报告")
        return {}
    logger.info("[维保Agent] Replanner 生成最终报告")
    return {"response": _build_report(state)}


def _build_report(state: PlanState) -> str:
    """汇总执行步骤生成维保报告（真实 LLM 可优化措辞，第一版模板化）"""
    steps = state.get("past_steps", [])
    lines = ["# 智能维保计划", ""]
    for task, result in steps:
        lines.append(f"## {task}")
        lines.append("")
        lines.append(result)
        lines.append("")
    lines.append("> 说明：以上数据来自实时查询。维保时段建议结合仓库忙闲（busy_level 越小越闲）错峰安排。")
    return "\n".join(lines)
