"""智能查询 Agent：LangGraph ReAct 状态图（决策 → 调工具 → 循环 → 总结）

参考 onecall 的 rag_agent_service，但用新版 LangGraph API 手写：
- 节点 agent：LLM 决定调用哪些工具
- 节点 tools：执行工具调用，结果回填
- 条件边：还有 tool_calls 就继续，否则结束
- MemorySaver 按 session_id 保存多轮会话
"""

import json
from collections.abc import AsyncGenerator
from typing import Annotated, Any, TypedDict, cast

import redis as redis_lib
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from loguru import logger

from app.agent.llm import get_chat_model
from app.config import config
from app.tools import ALL_AGENT_TOOLS

# 会话历史 Redis 持久化（TTL 7 天；RedisSaver 需要 RediSearch 模块，
# 本机 Redis 无该模块，故用 redis-py 直接存 JSON 列表）
HISTORY_TTL_SECONDS = 7 * 24 * 3600
_redis: redis_lib.Redis | None = None


def _get_redis() -> redis_lib.Redis:
    global _redis
    if _redis is None:
        _redis = redis_lib.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            decode_responses=True,
        )
    return _redis


def _history_key(session_id: str) -> str:
    return f"agent:history:{session_id}"

SYSTEM_PROMPT = """你是仓维云智能运维助手，帮助仓储管理人员查询设备运行状态。

工作原则：
1. 根据用户问题选择合适的工具查询实时数据，不要编造数据
2. 工具返回结果后，用简洁、清晰的中文总结给用户
3. 用户问题与业务无关时，礼貌说明你能做什么
4. 回答要具体：设备名、数值、状态、时间都要保留

工具选择规则（重要）：
- 问题包含"怎么排查/如何处理/步骤/方法/规范/保养/维护/手册"等知识性内容
  → 必须使用 retrieve_knowledge 工具检索维保知识库
- 问题涉及"当前状态/实时数据/有哪些"等业务查询
  → 使用业务工具（query_device_health/query_alerts/query_work_orders/query_spare_parts/query_devices/get_busy_window）
- 两者结合的问题（如"按手册排查某设备过热"）→ 先 retrieve_knowledge 再查业务数据

可用能力：
- 设备台账、设备健康度
- 告警记录（阈值/趋势告警）
- 工单列表与状态
- 备件库存与低库存预警
- 仓库忙闲时段（维保错峰参考）
- 融合诊断（振动+温度+电流联合判定故障模式）
- 维保知识库（手册、故障排查方法、操作规范）"""


class ChatState(TypedDict):
    """对话状态"""

    messages: Annotated[list[BaseMessage], add_messages]
    step_count: int


def _init_state(question: str) -> ChatState:
    return {"messages": [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=question)], "step_count": 0}


def _tool_call_ids(msg: BaseMessage) -> set[str]:
    """提取消息中的工具调用 ID（忽略无 id 的调用）"""
    return {str(call.get("id", "")) for call in getattr(msg, "tool_calls", []) or [] if call.get("id")}


def _sanitize_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """清洗发给 LLM 的消息历史，保证 tool_calls 与 ToolMessage 严格配对。

    历史中一旦残留"带 tool_calls 但没有对应工具结果"的孤儿消息（并发写入、
    流中断、模型返回异常 tool_call 等都可能造成），DeepSeek API 会直接 400，
    且会一直污染该会话，后续每次请求都失败。此函数在每次调用 LLM 前自愈：
    1. 只保留一条 SystemMessage 并置于最前；
    2. 剔除孤儿 tool_calls（保留其文本正文）；
    3. 丢弃没有来源的孤立 ToolMessage。
    """
    system: SystemMessage | None = None
    body: list[BaseMessage] = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            if system is None:
                system = msg
            continue
        body.append(msg)

    cleaned: list[BaseMessage] = []
    for idx, msg in enumerate(body):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            # 收集该消息之后出现的所有 ToolMessage id
            later_ids = {
                tm.tool_call_id
                for tm in body[idx + 1 :]
                if isinstance(tm, ToolMessage) and tm.tool_call_id
            }
            call_ids = _tool_call_ids(msg)
            # 无 id 的调用无法配对，同样视为孤儿
            missing = call_ids - later_ids
            if missing:
                content = msg.content if isinstance(msg.content, str) else ""
                logger.warning(f"[Agent] 历史中发现孤儿 tool_calls（{sorted(missing)[:3]}），已剔除并保留正文")
                cleaned.append(AIMessage(content=content))
            else:
                cleaned.append(msg)
        elif isinstance(msg, ToolMessage):
            # 只保留其前存在对应 AI(tool_calls) 的 ToolMessage
            matched = msg.tool_call_id and any(
                msg.tool_call_id in _tool_call_ids(pm) for pm in body[:idx] if isinstance(pm, AIMessage)
            )
            if matched:
                cleaned.append(msg)
            else:
                logger.warning(f"[Agent] 丢弃孤立 ToolMessage: {msg.tool_call_id}")
        else:
            cleaned.append(msg)

    # 去掉既无正文又无 tool_calls 的空 AI 占位消息
    cleaned = [
        msg
        for msg in cleaned
        if not (
            isinstance(msg, AIMessage)
            and not getattr(msg, "tool_calls", None)
            and not str(msg.content or "").strip()
        )
    ]
    if system is not None:
        cleaned.insert(0, system)
    return cleaned


async def _agent_node(state: ChatState) -> dict[str, Any]:
    """LLM 决策节点：可能输出文本，也可能带 tool_calls"""
    llm = get_chat_model().bind_tools(ALL_AGENT_TOOLS)
    response = await llm.ainvoke(_sanitize_messages(list(state["messages"])))
    return {"messages": [response], "step_count": state["step_count"] + 1}


def _should_continue(state: ChatState) -> str:
    """还有工具调用就进 tools；达到步数上限或没有调用则结束"""
    last = state["messages"][-1]
    if state["step_count"] >= config.agent_max_steps:
        logger.warning("对话 Agent 达到步数上限，强制结束")
        return END
    if getattr(last, "tool_calls", None):
        return "tools"
    return END


async def _tools_node(state: ChatState) -> dict[str, Any]:
    """执行 LLM 请求的工具调用，返回 ToolMessage 列表"""
    last = state["messages"][-1]
    tool_map = {t.name: t for t in ALL_AGENT_TOOLS}
    tool_messages: list[ToolMessage] = []
    for call in getattr(last, "tool_calls", []) or []:
        tool = tool_map.get(call.get("name", ""))
        if tool is None:
            content = f"未找到工具: {call.get('name')}"
        else:
            try:
                logger.info(f"[Agent] 调用工具 {tool.name}: {call.get('args')}")
                content = str(await tool.ainvoke(call.get("args", {})))
            except Exception as exc:  # noqa: BLE001
                logger.exception(f"[Agent] 工具 {tool.name} 调用失败")
                content = f"工具调用失败: {exc}"
        tool_messages.append(
            ToolMessage(
                content=content,
                tool_call_id=call.get("id") or "",
                name=call.get("name", ""),
            )
        )
    return {"messages": tool_messages}


_workflow = StateGraph(ChatState)
_workflow.add_node("agent", _agent_node)
_workflow.add_node("tools", _tools_node)
_workflow.add_edge(START, "agent")
_workflow.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
_workflow.add_edge("tools", "agent")

_checkpointer = MemorySaver()
agent_graph = _workflow.compile(checkpointer=_checkpointer)


def clear_session(session_id: str) -> bool:
    """清空会话历史"""
    try:
        _checkpointer.delete_thread(session_id)
        _get_redis().delete(_history_key(session_id))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"清空会话失败: {exc}")
        return False


def _collect_messages(session_id: str) -> list[dict]:
    """从 MemorySaver 收集当前会话消息（不含系统消息、空内容）"""
    config: RunnableConfig = {"configurable": {"thread_id": session_id}}
    try:
        checkpoint_tuple = _checkpointer.get_tuple(config)
        if checkpoint_tuple is None:
            return []
        channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
        messages = channel_values.get("messages", []) or []
        history: list[dict] = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                continue
            if isinstance(msg, (HumanMessage, AIMessage)):
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                if not content.strip():
                    continue
                item: dict = {
                    "role": "user" if isinstance(msg, HumanMessage) else "assistant",
                    "content": content,
                }
                tool_calls = getattr(msg, "tool_calls", None) or []
                if tool_calls:
                    item["tools"] = [tc.get("name", "") for tc in tool_calls]
                history.append(item)
        return history
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"读取会话历史失败: {exc}")
        return []


def save_session_history(session_id: str) -> None:
    """把当前会话消息写入 Redis（覆盖写 + 7 天 TTL）"""
    history = _collect_messages(session_id)
    key = _history_key(session_id)
    try:
        r = _get_redis()
        r.delete(key)
        if history:
            payload = [json.dumps(item, ensure_ascii=False) for item in history]
            r.rpush(key, *payload)
            r.expire(key, HISTORY_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"写入 Redis 会话历史失败: {exc}")


def get_session_history(session_id: str) -> list[dict]:
    """读取会话历史：优先 Redis（跨重启持久），兜底 MemorySaver"""
    try:
        items = cast(list, _get_redis().lrange(_history_key(session_id), 0, -1))
        if items:
            return [json.loads(item) for item in items]
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"读取 Redis 会话历史失败: {exc}")
    return _collect_messages(session_id)


async def _emit_updates(payload: dict) -> AsyncGenerator[dict[str, Any], None]:
    """updates 模式：节点级事件（工具调用、工具结果）"""
    for _node_name, output in payload.items():
        output = output or {}
        for message in output.get("messages", []) or []:
            if isinstance(message, AIMessage):
                for call in getattr(message, "tool_calls", []) or []:
                    yield {"type": "tool_call", "data": call.get("name", "")}
            elif isinstance(message, ToolMessage):
                yield {
                    "type": "tool_result",
                    "data": str(message.content)[:2000],
                    "tool": message.name or "",
                }


async def _graph_events(question: str, session_id: str) -> AsyncGenerator[dict[str, Any], None]:
    """遍历 LangGraph 事件：messages 模式逐 token 输出，updates 模式输出工具事件"""
    graph_config: RunnableConfig = {"configurable": {"thread_id": session_id}}
    async for event in agent_graph.astream(
        _init_state(question),
        config=graph_config,
        stream_mode=["updates", "messages"],
    ):
        if not isinstance(event, tuple) or len(event) != 2:
            continue
        mode, payload = event
        if mode == "messages" and isinstance(payload, tuple) and len(payload) == 2:
            chunk, _metadata = payload
            if isinstance(chunk, AIMessageChunk) and chunk.content:
                yield {"type": "content", "data": str(chunk.content)}
        elif mode == "updates" and isinstance(payload, dict):
            async for event in _emit_updates(payload):
                yield event


async def chat_stream(question: str, session_id: str) -> AsyncGenerator[dict[str, Any], None]:
    """流式对话（token 级）：产出 content / tool_call / tool_result / complete / error 事件"""
    logger.info(f"[会话 {session_id}] Agent 收到问题: {question}")
    try:
        async for event in _graph_events(question, session_id):
            yield event
        save_session_history(session_id)
        yield {"type": "complete"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("[Agent] 对话流异常")
        yield {"type": "error", "data": str(exc)}


async def chat(question: str, session_id: str) -> str:
    """非流式对话：拼装最终回答"""
    answer_parts: list[str] = []
    async for event in chat_stream(question, session_id):
        if event["type"] == "content":
            answer_parts.append(str(event["data"]))
        elif event["type"] == "error":
            return f"出错了：{event['data']}"
    return "".join(answer_parts) if answer_parts else "（暂无回答，请换个问法）"
