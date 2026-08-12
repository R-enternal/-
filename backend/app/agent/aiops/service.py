"""维保计划 Agent 服务：Plan-Execute-Replan 编排（流式事件）"""

from collections.abc import AsyncGenerator
from typing import Any

from langgraph.graph import END, START, StateGraph
from loguru import logger

from app.agent.aiops.executor import executor
from app.agent.aiops.planner import planner
from app.agent.aiops.replanner import replanner
from app.agent.aiops.state import PlanState


async def _should_continue(state: PlanState) -> str:
    if state.get("response"):
        return END
    return "executor" if state.get("plan") else END


_workflow = StateGraph(PlanState)
_workflow.add_node("planner", planner)
_workflow.add_node("executor", executor)
_workflow.add_node("replanner", replanner)
_workflow.add_edge(START, "planner")
_workflow.add_edge("planner", "executor")
_workflow.add_edge("executor", "replanner")
_workflow.add_conditional_edges("replanner", _should_continue, {"executor": "executor", END: END})
plan_graph = _workflow.compile()


async def run_plan(task: str) -> AsyncGenerator[dict[str, Any], None]:
    """执行维保计划流程，产出 plan / step_complete / report / complete / error 事件"""
    logger.info(f"[维保Agent] 收到任务: {task}")
    initial: PlanState = {"input": task, "plan": [], "past_steps": [], "response": "", "step_count": 0}
    try:
        async for event in plan_graph.astream(initial, stream_mode="updates"):
            for node_name, output in event.items():
                output = output or {}
                if node_name == "planner" and output.get("plan"):
                    yield {"type": "plan", "data": output["plan"]}
                elif node_name == "executor" and output.get("past_steps"):
                    step, result = output["past_steps"][-1]
                    yield {"type": "step_complete", "step": step, "data": str(result)[:5000]}
                elif node_name == "replanner" and output.get("response"):
                    yield {"type": "report", "data": output["response"]}
        yield {"type": "complete"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("[维保Agent] 流程异常")
        yield {"type": "error", "data": str(exc)}
