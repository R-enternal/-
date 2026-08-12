"""融合诊断验收：纯函数单测 + 端到端接口"""

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import fusion_engine  # noqa: E402

BASE = "http://127.0.0.1:9901"


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post(path: str) -> dict:
    req = urllib.request.Request(BASE + path, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_pure() -> None:
    normal = [3.0 + i * 0.01 for i in range(20)]
    vibration_fault = [3.0 + i * 0.4 for i in range(20)]  # 振动加剧 → 轴承磨损
    temp_fault = [50.0 + i * 2.0 for i in range(20)]  # 温度爬升 → 电机过热
    current_fault = [28.0 + (i % 4) * 6.0 for i in range(20)]  # 电流大波动 → 负载异常

    r = fusion_engine.diagnose(
        vibration_values=vibration_fault,
        temperature_values=normal,
        current_values=normal,
        vibration_high=7.1,
        temperature_high=85.0,
        current_high=50.0,
    )
    assert r.fault_type == "BEARING_WEAR", r
    print(f"[单测① 振动异常] {r.fault_type} 置信度 {r.confidence} OK")

    r = fusion_engine.diagnose(
        vibration_values=normal,
        temperature_values=temp_fault,
        current_values=normal,
        vibration_high=7.1,
        temperature_high=85.0,
        current_high=50.0,
    )
    assert r.fault_type == "MOTOR_OVERHEAT", r
    print(f"[单测② 温度异常] {r.fault_type} 置信度 {r.confidence} OK")

    r = fusion_engine.diagnose(
        vibration_values=normal,
        temperature_values=normal,
        current_values=current_fault,
        vibration_high=7.1,
        temperature_high=85.0,
        current_high=50.0,
    )
    assert r.fault_type == "LOAD_ABNORMAL", r
    print(f"[单测③ 电流异常] {r.fault_type} 置信度 {r.confidence} OK")

    r = fusion_engine.diagnose(
        vibration_values=vibration_fault,
        temperature_values=temp_fault,
        current_values=normal,
        vibration_high=7.1,
        temperature_high=85.0,
        current_high=50.0,
    )
    assert r.fault_type == "COMPOSITE_FAULT", r
    print(f"[单测④ 多信号异常] {r.fault_type} 置信度 {r.confidence} OK")

    r = fusion_engine.diagnose(
        vibration_values=normal,
        temperature_values=normal,
        current_values=normal,
        vibration_high=7.1,
        temperature_high=85.0,
        current_high=50.0,
    )
    assert r.fault_type == "NORMAL", r
    print(f"[单测⑤ 正常] {r.fault_type} OK")


def test_e2e() -> None:
    result = post("/api/diagnosis/run")
    print(f"[端到端① 批量诊断] {result.get('data', {}).get('devices')} 台设备")
    records = get("/api/diagnosis").get("data", [])
    assert records, "无诊断记录"
    print(f"[端到端② 诊断列表] {len(records)} 条，最新: {records[0]['fault_type']} 置信度 {records[0]['confidence']}")


def main() -> None:
    test_pure()
    test_e2e()
    print("\n========== 融合诊断验收通过 ==========")


if __name__ == "__main__":
    main()
