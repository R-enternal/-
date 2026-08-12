"""诊断 DeepSeek 工具调用：直接绑定工具提问，打印完整响应"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402

from app.agent.chat_agent import SYSTEM_PROMPT  # noqa: E402
from app.agent.llm import get_chat_model  # noqa: E402
from app.tools import ALL_AGENT_TOOLS  # noqa: E402


async def main() -> None:
    llm = get_chat_model().bind_tools(ALL_AGENT_TOOLS)
    print("工具数:", len(ALL_AGENT_TOOLS))
    for name in [t.name for t in ALL_AGENT_TOOLS]:
        print(" -", name)
    resp = await llm.ainvoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content="有哪些待处理告警"),
        ]
    )
    print("\ncontent:", repr(resp.content)[:300])
    print("tool_calls:", resp.tool_calls)
    print("usage:", getattr(resp, "usage_metadata", None))


if __name__ == "__main__":
    asyncio.run(main())
