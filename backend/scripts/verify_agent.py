"""Agent 模块验收脚本：验证工具/对话/维保计划/落库/调度接口

用法（backend 目录下，先启动服务）：python scripts/verify_agent.py
"""

import json
import urllib.request

BASE = "http://127.0.0.1:9901"


def safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("gbk", errors="ignore").decode("gbk"))


def post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    # 1. 对话接口连通性（空问题被校验拦截也算连通）
    resp = post("/api/agent/chat", {"session_id": "verify", "question": "你好"})
    assert resp.get("code") == 200
    safe_print("[① 对话接口] 可用 OK")

    # 2. 智能查询（非流式）
    resp = post("/api/agent/chat", {"session_id": "verify", "question": "有哪些待处理告警"})
    safe_print(f"[② 智能查询] {resp.get('data', {}).get('answer', '')[:120]}...")

    # 3. 维保建议（不落库）
    resp = get("/api/agent/maintenance-suggestions")
    suggestions = resp.get("data", [])
    assert resp.get("code") == 200
    safe_print(f"[③ 维保建议] {len(suggestions)} 条，首条: {suggestions[0]['title'] if suggestions else '无'}")

    # 4. 维保计划落库
    resp = post("/api/agent/maintenance-plans/save", {"plan_date": None})
    saved = resp.get("data", {}).get("saved", 0)
    safe_print(f"[④ 计划落库] {saved} 条")

    # 5. 计划列表 + 首条转工单
    plans = get("/api/agent/maintenance-plans").get("data", [])
    if plans:
        resp = post(f"/api/agent/maintenance-plans/{plans[0]['id']}/convert", {})
        safe_print(f"[⑤ 转工单] {resp.get('message')}")

    # 6. 调度建议
    resp = get("/api/agent/assign-suggestions")
    safe_print(f"[⑥ 调度建议] {len(resp.get('data', []))} 条")

    safe_print("\n========== Agent 验收通过 ==========")


if __name__ == "__main__":
    main()
