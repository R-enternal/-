"""验证 token 级流式输出：统计 content 事件数量（>1 即真流式）"""

import json
import time
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
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    events = []
    for block in raw.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def main() -> None:
    sid = f"stream-{int(time.time())}"
    events = sse("/api/agent/chat_stream", {"session_id": sid, "question": "有哪些待处理告警"})
    types = [e["type"] for e in events]
    contents = [e["data"] for e in events if e["type"] == "content"]
    print("事件类型:", types)
    print(f"content 事件数: {len(contents)}（>1 表示逐 token 流式）")
    print("拼接回答长度:", len("".join(contents)))
    assert "tool_call" in types, "未调用工具"
    assert len(contents) > 1, "不是真流式（content 事件过少）"
    print("\n========== 流式验收通过 ==========")


if __name__ == "__main__":
    main()
