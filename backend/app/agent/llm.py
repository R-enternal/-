"""Agent LLM 工厂

OpenAI 兼容接口；未配置 LLM_API_KEY 时返回规则降级模型，
保证在没有 API Key 的环境下也能完整演示"Agent 调工具 → 总结"链路。
"""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config import config


def get_chat_model() -> BaseChatModel:
    """按配置返回真实 LLM 或规则降级模型"""
    if config.llm_api_key:
        return ChatOpenAI(
            model=config.llm_model,
            api_key=SecretStr(config.llm_api_key),
            base_url=config.llm_base_url,
            temperature=0,
        )
    return RuleBasedChatModel()


# 关键词 → 工具路由（降级模型用；真实 LLM 靠工具 description 自主选择）
_TOOL_ROUTES: list[tuple[tuple[str, ...], str, dict[str, Any]]] = [
    (("健康度", "健康", "亚健康", "异常"), "query_device_health", {}),
    (("告警", "预警"), "query_alerts", {"status": "PENDING"}),
    (("工单",), "query_work_orders", {"status": ""}),
    (("备件", "库存", "安全库存"), "query_spare_parts", {"low_stock_only": False}),
    (("设备", "几台", "台账"), "query_devices", {"status": ""}),
    (("忙", "闲", "忙闲", "维保时间"), "get_busy_window", {"weekday": None}),
    (("怎么", "如何", "排查", "手册", "知识", "规范", "保养方法"), "retrieve_knowledge", {"query": ""}),
]


def _route_tool(text: str) -> dict[str, Any] | None:
    """按关键词匹配工具调用（降级模型）"""
    for keywords, name, args in _TOOL_ROUTES:
        if any(k in text for k in keywords):
            if name == "retrieve_knowledge":
                args = {"query": text}
            return {"name": name, "args": args, "id": "call_rule_1"}
    return None


def _summarize_tool(message: ToolMessage) -> str:
    """把工具结果整理成回复（降级模型）"""
    name = message.name or "工具"
    return (
        f"根据{name}的查询结果：\n\n{message.content}\n\n"
        "（当前为离线规则模式，配置 LLM_API_KEY 后可获得更自然的回答。）"
    )


class RuleBasedChatModel(BaseChatModel):
    """无 API Key 时的降级模型：关键词路由 → 工具调用 → 结果总结"""

    @property
    def _llm_type(self) -> str:
        return "rule-based"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model": "rule-based"}

    def bind_tools(self, tools: Any, **kwargs: Any) -> BaseChatModel:  # noqa: ARG002
        """降级模型不依赖工具 schema，直接返回自身"""
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,  # noqa: ARG002
        run_manager: Any = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> ChatResult:
        last = messages[-1]
        if isinstance(last, ToolMessage):
            content = _summarize_tool(last)
        elif isinstance(last, (HumanMessage, SystemMessage)):
            tool_call = _route_tool(str(last.content))
            if tool_call is not None:
                return ChatResult(
                    generations=[
                        ChatGeneration(message=AIMessage(content="", tool_calls=[tool_call]))
                    ]
                )
            content = (
                "我是仓脉智诊智能运维助手，可以帮你查询设备健康度、告警、工单、备件，"
                "或生成智能维保计划。试试问我：'1号输送线健康度怎么样？'、'有哪些待处理告警？'"
            )
        else:
            content = "我还在处理，请稍后再问。"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])
