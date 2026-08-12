"""设备域 API 端到端自测

流程：启动服务 → 建仓库 → 建输送机 → 验证自动带出点位 → 查询/更新/删除
运行方式（backend 目录下）：python scripts/test_device_api.py
"""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:9901"


def request(method: str, path: str, body: dict | None = None) -> dict:
    """发送 HTTP 请求并返回 JSON"""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 错误响应体也按统一格式 {code, message, data} 返回
        return json.loads(e.read().decode("utf-8"))


def wait_ready(timeout: int = 15) -> bool:
    """等待服务就绪"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            request("GET", "/health")
            return True
        except Exception:
            time.sleep(0.5)
    return False


def test_device_api_flow() -> None:
    # 每次运行生成唯一后缀，保证脚本可重复执行（幂等）
    run_suffix = str(int(time.time()))

    # 1. 启动服务
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "9901"],
        cwd=str(BACKEND_DIR),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"服务已启动 PID={proc.pid}，等待就绪...")
    if not wait_ready():
        print("服务启动超时")
        proc.terminate()
        sys.exit(1)
    print("服务就绪 OK")

    warehouse_id = None
    device_id = None
    try:
        # 2. 建仓库
        wh = request(
            "POST",
            "/api/warehouses",
            {
                "name": "合肥示范仓",
                "address": "合肥市经开区",
                "contact_name": "张工",
                "contact_phone": "13800000000",
            },
        )
        print("\n[建仓库]", json.dumps(wh, ensure_ascii=False))
        warehouse_id = wh["data"]["id"]

        # 3. 建输送机（auto_create_points 默认 True）
        dev = request(
            "POST",
            "/api/devices",
            {
                "warehouse_id": warehouse_id,
                "device_code": f"CV-{run_suffix}",
                "name": "1号输送线",
                "device_type": "CONVEYOR",
                "brand": "中科仓储",
                "model": "ZB-500",
                "location": "A区01号",
                "install_date": "2025-06-01",
                "lifespan_years": 10,
            },
        )
        print("\n[建输送机]", json.dumps(dev, ensure_ascii=False))
        device_id = dev["data"]["id"]
        points = dev["data"]["points"]
        print(f"\n自动带出点位 {len(points)} 个：")
        for p in points:
            print(
                f"  {p['point_code']:16s} {p['point_type']:12s} "
                f"阈值[{p['alarm_low']}~{p['alarm_high']}] "
                f"窗口{p['trend_window']} 幅度{p['trend_delta']}"
            )

        # 4. 设备详情
        detail = request("GET", f"/api/devices/{device_id}")
        print("\n[设备详情] 点位数量:", len(detail["data"]["points"]))

        # 5. 点位覆盖：单独调高 1 号线的温度阈值
        temp_point = next(p for p in points if p["point_type"] == "TEMPERATURE")
        upd = request(
            "PUT",
            f"/api/devices/points/{temp_point['id']}",
            {
                "alarm_high": 90.0,
            },
        )
        print("\n[点位阈值覆盖] 温度阈值 ->", upd["data"]["alarm_high"])

        # 6. 设备列表按类型过滤
        lst = request("GET", "/api/devices?device_type=CONVEYOR")
        print("\n[输送机列表] 数量:", len(lst["data"]))

        # 7. 修复验证①：update_device 改重编号应返回 400（而不是 500）
        dev_dup = request(
            "POST",
            "/api/devices",
            {
                "warehouse_id": warehouse_id,
                "device_code": f"CV-DUP-{run_suffix}",
                "name": "查重测试设备",
                "device_type": "CONVEYOR",
            },
        )
        dup_id = dev_dup["data"]["id"]
        dup_resp = request(
            "PUT",
            f"/api/devices/{dup_id}",
            {"device_code": dev["data"]["device_code"]},
        )
        assert dup_resp["code"] == 400, f"期望 400，实际 {dup_resp}"
        print("\n[修复① 改重编号] code =", dup_resp["code"], "|", dup_resp["message"])
        request("DELETE", f"/api/devices/{dup_id}")

        # 8. 修复验证②：小写 device_type 应返回 422（Literal 校验）
        bad_type = request(
            "POST",
            "/api/devices",
            {
                "warehouse_id": warehouse_id,
                "device_code": f"CV-LOW-{run_suffix}",
                "name": "小写类型测试",
                "device_type": "conveyor",
            },
        )
        assert bad_type["code"] == 422, f"期望 422，实际 {bad_type}"
        print("\n[修复② 小写类型] code =", bad_type["code"], "|", bad_type["message"])

        # 9. 修复验证③：统一异常响应格式（404 也返回 {code, message, data}）
        not_found = request("GET", "/api/devices/999999")
        assert not_found["code"] == 404 and "data" in not_found
        print("\n[修复③ 统一异常格式] code =", not_found["code"], "|", not_found["message"])

        # 10. 删除临时设备
        dev2 = request(
            "POST",
            "/api/devices",
            {
                "warehouse_id": warehouse_id,
                "device_code": f"CV-TMP-{run_suffix}",
                "name": "临时设备",
                "device_type": "CONVEYOR",
            },
        )
        tmp_id = dev2["data"]["id"]
        del_resp = request("DELETE", f"/api/devices/{tmp_id}")
        print("\n[删除临时设备]", del_resp["message"])

        print("\n========== 全部测试通过 ==========")
    finally:
        # 清理测试数据：主设备 + 仓库（防止重复运行累积残留）
        if device_id is not None:
            try:
                request("DELETE", f"/api/devices/{device_id}")
                print(f"已清理测试设备 {device_id}")
            except Exception:  # noqa: BLE001
                print(f"清理设备 {device_id} 失败（可能已被删除）")
        if warehouse_id is not None:
            try:
                request("DELETE", f"/api/warehouses/{warehouse_id}")
                print(f"已清理测试仓库 {warehouse_id}")
            except Exception:  # noqa: BLE001
                print(f"清理仓库 {warehouse_id} 失败")
        proc.terminate()
        print("测试结束，服务已停止")


if __name__ == "__main__":
    test_device_api_flow()
