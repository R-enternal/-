"""知识检索工具：从 Chroma 知识库语义检索维保资料"""

from langchain_core.tools import tool
from loguru import logger

from app.services import kb_service


@tool
def retrieve_knowledge(query: str) -> str:
    """从维保知识库检索相关文档资料。

    当用户的问题涉及维保手册、故障排查方法、操作规范、维护步骤等知识性内容时使用，
    例如"电机过热怎么排查""输送机如何保养""AGV 电池维护规范"。

    Args:
        query: 检索关键词或问题描述
    """
    logger.info(f"[知识库] 检索: {query}")
    return kb_service.search_as_context(query)
