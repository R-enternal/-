"""第 18 步验收：前后端联调完整业务流

通过前端 vite proxy（5173 → 9901）走完整链路：
    模拟数据 → 产生告警 → 确认告警 → 转工单 → 派单 → 执行 → 验收 → 完成

数据准备/清理直接操作数据库（灌超限数据），业务动作全部走 HTTP。
运行方式（backend 目录下）：python scripts/verify_e2e.py
"""

import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.device import Device, DevicePoint  # noqa: E402
from app.models.monitor import Alert, SensorData  # noqa: E402
from app.models.user import Notification  # noqa: E402
from app.models.warehouse import Warehouse  # noqa: E402
from app.models.work_order import WorkOrder  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend"
BASE = "http://127.0.0.1:5173/api"


def http_json(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode("utf-8"))


def wait_ready(url: str, timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except Exception:
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
    db = SessionLocal()
    suffix = str(int(datetime.now().timestamp()))
    wh = device = point = None
    try:
        assert wait_ready("http://127.0.0.1:9901/health"), "后端未就绪"
        assert wait_ready("http://127.0.0.1:5173/"), "前端未就绪"
        print("[准备] 前后端就绪")

        # 1. 数据准备：测试设备 + 点位 + 3 条超限数据（DB）
        wh = Warehouse(name=f"E2E测试仓-{suffix}")
        db.add(wh)
        db.flush()
        device = Device(
            warehouse_id=wh.id,
            device_code=f"E2E-{suffix}",
            name="联调测试设备",
            device_type="CONVEYOR",
        )
        db.add(device)
        db.flush()
        point = DevicePoint(
            device_id=device.id,
            point_code="E2E-TEMP",
            point_type="TEMPERATURE",
            unit="℃",
            alarm_high=50.0,
            trend_window=30,
            trend_delta=8.0,
        )
        db.add(point)
        db.flush()
        base_time = datetime.now().replace(microsecond=0)
        for i in range(3):
            db.add(
                SensorData(
                    device_id=device.id,
                    device_point_id=point.id,
                    value=60.0 + i,
                    collected_at=base_time - timedelta(minutes=2 - i),
                )
            )
        db.commit()
        print("[步骤① 模拟数据] 灌入 3 条超限数据（60/61/62℃，阈值 50）")

        # 2. HTTP：触发告警检查
        r = http_json("POST", "/alerts/check")
        assert r.get("code") == 200
        alert = db.scalar(select(Alert).where(Alert.point_id == point.id))
        assert alert is not None, "未生成告警"
        alert_id = alert.id
        print(
            f"[步骤② 产生告警] #{alert_id} {alert.alert_type}（{alert.metric_value} > {alert.threshold}）"
        )

        # 3. HTTP：确认告警
        r = http_json(
            "POST", f"/alerts/{alert_id}/handle", {"handled_by": "admin", "handle_note": "联调确认"}
        )
        assert r.get("code") == 200
        print(f"[步骤③ 确认告警] {r['message']}")

        # 4. HTTP：转工单
        r = http_json("POST", f"/alerts/{alert_id}/convert")
        assert r.get("code") == 200
        order_id = r["data"]["id"]
        print(f"[步骤④ 转工单] {r['data']['order_no']}（source=ALERT）")

        # 5. HTTP：派单（选第一个用户）
        r = http_json("GET", "/auth/users")
        assert r.get("code") == 200 and r["data"]
        assignee_id = r["data"][0]["id"]
        r = http_json(
            "POST",
            f"/work-orders/{order_id}/transition",
            {"action": "assign", "assignee_id": assignee_id},
        )
        assert r.get("code") == 200
        print(f"[步骤⑤ 派单] → PENDING_EXECUTE（指派人 #{assignee_id}）")

        # 6. HTTP：执行 → 提交 → 完成
        for action in ["start", "submit"]:
            r = http_json("POST", f"/work-orders/{order_id}/transition", {"action": action})
            assert r.get("code") == 200
        r = http_json(
            "POST",
            f"/work-orders/{order_id}/transition",
            {"action": "complete", "result": "联调完成"},
        )
        assert r.get("code") == 200 and r["data"]["status"] == "COMPLETED"
        print("[步骤⑥ 执行→验收→完成] → COMPLETED")

        # 7. 前端页面可访问（五个路由）
        for path in ["/dashboard", "/devices", "/alerts", "/work-orders", "/spare-parts"]:
            with urllib.request.urlopen(f"http://127.0.0.1:5173{path}", timeout=5):
                pass
        print("[步骤⑦ 五个页面] 均可访问")

        print("\n========== 前后端联调完整业务流通过 ==========")
    finally:
        db.rollback()
        if wh is not None and device is not None and point is not None:
            alert_ids = list(db.scalars(select(Alert.id).where(Alert.device_id == device.id)))
            order_ids = list(
                db.scalars(select(WorkOrder.id).where(WorkOrder.device_id == device.id))
            )
            if alert_ids or order_ids:
                db.query(Notification).filter(
                    Notification.ref_id.in_(alert_ids + order_ids)
                ).delete()
            db.query(WorkOrder).filter(WorkOrder.device_id == device.id).delete()
            db.query(Alert).filter(Alert.device_id == device.id).delete()
            db.query(SensorData).filter(SensorData.device_id == device.id).delete()
            db.query(DevicePoint).filter(DevicePoint.id == point.id).delete()
            db.query(Device).filter(Device.id == device.id).delete()
            db.query(Warehouse).filter(Warehouse.id == wh.id).delete()
            db.commit()
        db.close()
        for p in procs:
            p.terminate()
        print("验证结束，服务已停止")


if __name__ == "__main__":
    main()
