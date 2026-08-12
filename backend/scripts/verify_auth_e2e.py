"""第 19 步验收：auth_enabled=True 时认证全链路

通过环境变量 AUTH_ENABLED=true 启动后端（不修改 .env 默认值），验证：
1. 未带 token 访问业务接口 → 401
2. 登录拿 token → 带 token 访问 → 200
3. 公开路径（/health）免认证

前置：先运行 scripts/seed_demo.py（含演示账号）。
运行方式（backend 目录下）：python scripts/verify_auth_e2e.py
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:9901"


def http_json(
    method: str, path: str, body: dict | None = None, token: str | None = None
) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def main() -> None:
    env = os.environ.copy()
    env["AUTH_ENABLED"] = "true"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "9901"],
        cwd=str(BACKEND_DIR),
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # 等待就绪
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"{BASE}/health", timeout=2):
                    break
            except Exception:
                time.sleep(0.5)
        else:
            raise AssertionError("后端未就绪")
        print("[准备] 后端已以 AUTH_ENABLED=true 启动")

        # 1. 无 token → 401
        status, body = http_json("GET", "/api/devices")
        assert status == 401 and body["code"] == 401
        print("[验证① 未认证] 无 token 访问 /api/devices → 401 OK")

        # 2. 公开路径免认证
        status, _ = http_json("GET", "/health")
        assert status == 200
        print("[验证② 公开路径] /health 免认证 OK")

        # 3. 错误密码 → 401
        status, _ = http_json("POST", "/api/auth/login", {"username": "admin", "password": "wrong"})
        assert status == 401
        print("[验证③ 错误密码] 登录 401 OK")

        # 4. 正确登录 → 带 token 访问 → 200
        status, body = http_json(
            "POST", "/api/auth/login", {"username": "admin", "password": "admin123"}
        )
        assert status == 200
        token = body["data"]["token"]
        assert body["data"]["user"]["role"] == "ADMIN"
        status, body = http_json("GET", "/api/devices", token=token)
        assert status == 200 and body["code"] == 200
        print(f"[验证④ 登录+授权] 带 token 访问 → 200（{len(body['data'])} 台设备）OK")

        print("\n========== 认证全链路验证通过 ==========")
    finally:
        proc.terminate()
        print("验证结束，服务已停止")


if __name__ == "__main__":
    main()
