"""Planner 节点：把任务拆成执行计划"""

from textwrap import dedent
from typing import Any

from langchain_core.messages import SystemMessage
from loguru import logger

from app.agent.aiops.state import PlanState
from app.agent.llm import get_chat_model

_PLANNER_PROMPT = """你是仓储设备维保规划专家。请把任务拆解为 3-5 个可执行的步骤，每行一个步骤，直接输出步骤列表，不要多余说明。

任务：{task}

可选步骤素材（根据任务需要选择）：
- 查询设备健康度
- 查询待处理告警
- 查询备件库存
- 查询仓库忙闲时段
- 生成维保计划建议（按健康度/告警/忙闲错峰）
"""


def _default_plan() -> list[str]:
    """降级/失败时的默认计划"""
    return [
        "查询所有设备健康度",
        "查询待处理告警",
        "查询仓库忙闲时段",
        "生成维保计划建议",
    ]


async def planner(state: PlanState) -> dict[str, Any]:
    """制定执行计划（真实 LLM 生成；无 key 或失败时用默认计划）"""
    logger.info("[维保Agent] Planner 制定计划")
    task = state.get("input", "")
    plan = _default_plan()
    try:
        llm = get_chat_model()
        # 降级模型不产生规划文本时直接回落默认计划；真实 LLM 解析行
        resp = await llm.ainvoke(
            [SystemMessage(content=dedent(_PLANNER_PROMPT).format(task=task))]
        )
        text = str(resp.content).strip()
        if text and not text.startswith("我是仓维云"):
            lines = [line.strip("-* 0123456789.、)").strip() for line in text.splitlines() if line.strip()]
            plan = [line for line in lines if 4 <= len(line) <= 60][:5] or plan
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[维保Agent] Planner 失败，用默认计划: {exc}")
    logger.info(f"[维保Agent] 计划 {len(plan)} 步: {plan}")
    return {"plan": plan}
