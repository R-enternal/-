"""验证会话历史恢复：发一条对话 → 读取历史接口"""

import json
import time
import urllib.request

BASE = "http://127.0.0.1:9901"


def safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("gbk", errors="ignore").decode("gbk"))


def sse_post(path: str, payload: dict) -> list[dict]:
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
    sid = f"hist-{int(time.time())}"
    events = sse_post("/api/agent/chat_stream", {"session_id": sid, "question": "有哪些待处理告警"})
    assert any(e["type"] == "complete" for e in events), "对话未完成"
    time.sleep(0.5)

    with urllib.request.urlopen(f"{BASE}/api/agent/session/{sid}/history", timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    history = data.get("data", [])
    safe_print("历史条数: " + str(len(history)))
    for m in history:
        safe_print(f" - {m['role']} | tools: {m.get('tools', [])} | {m['content'][:60]}")
    assert len(history) >= 2, "历史应包含用户问题与助手回答"
    safe_print("\n========== 会话历史验收通过 ==========")


if __name__ == "__main__":
    main()
