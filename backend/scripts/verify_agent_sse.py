"""SSE 流式接口验证（对话 + 维保计划）"""

import json
import urllib.request

BASE = "http://127.0.0.1:9901"


def sse(path: str, payload: dict) -> list[dict]:
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    events = []
    for block in raw.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def main() -> None:
    events = sse("/api/agent/chat_stream", {"session_id": "sse-verify", "question": "有哪些待处理告警"})
    types = [e["type"] for e in events]
    assert "tool_call" in types and "complete" in types, f"对话 SSE 事件不完整: {types}"
    print(f"[① 对话 SSE] 事件: {types}")

    events = sse("/api/agent/plan_stream", {"session_id": "sse-verify", "task": "生成明天的维保计划"})
    types = [e["type"] for e in events]
    assert "plan" in types and "report" in types and "complete" in types, f"计划 SSE 事件不完整: {types}"
    print(f"[② 计划 SSE] 事件: {types}")
    report = next(e["data"] for e in events if e["type"] == "report")
    print(f"[③ 计划报告] 长度 {len(report)}，首行: {report.splitlines()[0]}")
    print("\n========== SSE 验收通过 ==========")


if __name__ == "__main__":
    main()
