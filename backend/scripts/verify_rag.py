"""RAG 知识库验收：真实模型对话 + 知识检索 + 上传接口"""

import json
import time
import urllib.request

BASE = "http://127.0.0.1:9901"


def safe_print(text: str) -> None:
    """控制台安全打印（GBK 环境下跳过无法编码的字符）"""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("gbk", errors="ignore").decode("gbk"))


def post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sse(path: str, payload: dict) -> list[dict]:
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    events = []
    for block in raw.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def main() -> None:
    sid = f"rag-{int(time.time())}"
    # 1. 知识问答（应触发 retrieve_knowledge 工具）
    events = sse("/api/agent/chat_stream", {"session_id": sid, "question": "电机过热怎么排查？"})
    tools = [e["data"] for e in events if e["type"] == "tool_call"]
    answers = [e["data"] for e in events if e["type"] == "content"]
    assert "retrieve_knowledge" in tools, f"未调用知识库工具: {tools}"
    full = "".join(answers)
    safe_print(f"[① 知识问答] 调用工具: {tools}")
    safe_print(f"[② 知识问答] 回答片段: {full[:150]}...")

    # 2. 业务查询（应走 DeepSeek 真实模型）
    events = sse("/api/agent/chat_stream", {"session_id": f"{sid}-2", "question": "有哪些待处理告警？"})
    tools = [e["data"] for e in events if e["type"] == "tool_call"]
    answers = [e["data"] for e in events if e["type"] == "content"]
    assert tools, "业务查询未调用工具"
    safe_print(f"[③ 业务查询] 调用工具: {tools}")
    safe_print(f"[④ 业务查询] 回答片段: {''.join(answers)[:150]}...")

    # 3. 上传接口（multipart）
    boundary = "----kbverify"
    content = "## 测试文档\n输送机链条每周润滑一次。\n"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="test.md"\r\n'
        "Content-Type: text/markdown\r\n\r\n"
        f"{content}\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(
        BASE + "/api/kb/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    safe_print(f"[⑤ 上传接口] {result.get('message')}")

    print("\n========== RAG 验收通过 ==========")


if __name__ == "__main__":
    main()
