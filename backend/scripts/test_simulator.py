"""模拟数据源验收测试

验证项：
1. 生成后 sensor_data 有条数 = 启用点位 × 分钟数
2. 数据包含 device_id / device_point_id / value / collected_at 基础字段
3. 异常注入有效：存在突破阈值的记录（为阈值引擎准备素材）

运行方式（backend 目录下）：python scripts/test_simulator.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.monitor import SensorData  # noqa: E402
from app.services import sensor_service  # noqa: E402

MINUTES = 300  # 300 分钟保证每个点位至少触发一次异常（90~150 周期）


def test_simulator_flow() -> None:
    db = SessionLocal()
    try:
        points = sensor_service.list_active_points(db)
        if not points:
            print("没有启用的点位，请先建设备")
            return
        print(f"启用点位: {len(points)} 个")

        # 1. 生成数据（固定种子，可复现）
        result = sensor_service.generate_history(db, minutes=MINUTES, seed=42)
        expect_rows = len(points) * MINUTES
        assert result["rows"] == expect_rows, f"写入条数 {result['rows']} != 期望 {expect_rows}"
        print(f"[验证① 条数] 写入 {result['rows']} 条 = 点位 {len(points)} × {MINUTES} 分钟 OK")

        # 2. 基础字段完整性
        sample = db.scalars(select(SensorData).limit(5)).all()
        for row in sample:
            assert row.device_id and row.device_point_id
            assert row.value is not None
            assert row.collected_at is not None
        print("[验证② 字段] device_id / device_point_id / value / collected_at 齐全 OK")

        # 3. 异常注入有效：存在突破 alarm_high 的记录
        over_count = 0
        for p in points:
            if p.alarm_high is None:
                continue
            cnt = db.scalar(
                select(func.count(SensorData.id)).where(
                    SensorData.device_point_id == p.id,
                    SensorData.value > p.alarm_high,
                )
            )
            over_count += cnt or 0
        assert over_count > 0, "没有发现突破阈值的记录，异常注入失效"
        print(f"[验证③ 异常注入] 突破阈值的记录共 {over_count} 条 OK")

        # 4. 时间戳落在预期窗口内
        newest = db.scalar(select(func.max(SensorData.collected_at)))
        oldest = db.scalar(select(func.min(SensorData.collected_at)))
        span = (newest - oldest).total_seconds() / 60
        print(f"[验证④ 时间窗] 最旧 {oldest:%H:%M} 最新 {newest:%H:%M}，跨度 {span:.0f} 分钟")
        assert span >= MINUTES - 1, f"时间跨度不足: {span}"

        # 5. seed 隔离：带 seed 调用不得替换全局模拟器（否则定时任务状态被重置）
        sim_before = sensor_service._get_simulator(None)
        sensor_service.generate_history(db, minutes=1, seed=42)
        sim_after = sensor_service._get_simulator(None)
        assert sim_before is sim_after, "带 seed 调用污染了全局模拟器"
        print("[验证⑤ seed 隔离] 带 seed 调用未替换全局实例 OK")

        print("\n========== 模拟器测试全部通过 ==========")
    finally:
        db.close()


if __name__ == "__main__":
    test_simulator_flow()
