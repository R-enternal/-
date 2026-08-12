"""第 17 步验收：前端骨架可运行 + 设备页调通后端

启动后端(9901) + 前端(5173)，检查：
1. 后端健康检查
2. 前端首页可访问
3. vite proxy：/api/devices 返回后端数据
4. SPA 路由 /devices 可访问（history 模式回退）

运行方式（backend 目录下）：python scripts/verify_frontend.py
"""

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"


def http_get(url: str, timeout: int = 5) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return 0, str(e)


def wait_ready(url: str, timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, _ = http_get(url, timeout=2)
        if status and status < 500:
            return True
        time.sleep(0.5)
    return False


def main() -> None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    procs = [
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "9901",
            ],
            cwd=str(BACKEND_DIR),
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
        subprocess.Popen(
            ["npm.cmd", "run", "dev", "--", "--host", "127.0.0.1"],
            cwd=str(FRONTEND_DIR),
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ),
    ]
    try:
        # 1. 后端
        assert wait_ready("http://127.0.0.1:9901/health"), "后端未就绪"
        print("[验证① 后端] /health OK")

        # 2. 前端
        assert wait_ready("http://127.0.0.1:5173/"), "前端未就绪"
        status, html = http_get("http://127.0.0.1:5173/")
        assert status == 200 and "仓维云" in html
        print("[验证② 前端] 首页可访问 OK")

        # 3. vite proxy → 后端设备接口
        status, body = http_get("http://127.0.0.1:5173/api/devices")
        assert status == 200, f"proxy 失败: {status}"
        data = json.loads(body)
        assert data.get("code") == 200
        print(f"[验证③ 代理调通] /api/devices 返回 {len(data.get('data', []))} 台设备 OK")

        # 4. SPA 路由回退
        status, html = http_get("http://127.0.0.1:5173/devices")
        assert status == 200 and 'id="app"' in html
        print("[验证④ SPA 路由] /devices 可访问 OK")

        print("\n========== 前端骨架验收全部通过 ==========")
    finally:
        for p in procs:
            p.terminate()
        print("验证结束，服务已停止")


if __name__ == "__main__":
    main()
