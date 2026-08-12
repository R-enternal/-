"""验证真实 LLM 链路：DeepSeek 对话 + 智谱 embedding"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.llm import get_chat_model  # noqa: E402
from app.config import config  # noqa: E402


def main() -> None:
    print(f"LLM: {config.llm_model} @ {config.llm_base_url}")
    print(f"Embedding: {config.embedding_model} @ {config.embedding_base_url}")

    # 1. DeepSeek 对话
    import asyncio

    async def chat_test() -> None:
        llm = get_chat_model()
        resp = await llm.ainvoke("用一句话介绍你自己")
        print("\n[DeepSeek 对话] OK:", str(resp.content)[:100])

    asyncio.run(chat_test())

    # 2. 智谱 embedding
    try:
        from langchain_openai import OpenAIEmbeddings

        emb = OpenAIEmbeddings(
            model=config.embedding_model,
            api_key=config.embedding_api_key,
            base_url=config.embedding_base_url,
        )
        vectors = emb.embed_documents(["仓储设备维保", "电机过热排查"])
        print(f"[智谱 Embedding] OK: 维度 {len(vectors[0])}")
    except Exception as exc:  # noqa: BLE001
        print(f"[智谱 Embedding] 失败: {exc}")


if __name__ == "__main__":
    main()
