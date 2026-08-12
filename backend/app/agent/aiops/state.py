"""Plan-Execute-Replan 状态定义（参考 onecall，适配新版 LangGraph）"""

import operator
from typing import Annotated, TypedDict


class PlanState(TypedDict):
    """维保计划状态"""

    input: str
    plan: list[str]
    past_steps: Annotated[list[tuple[str, str]], operator.add]
    response: str
    step_count: int
