"""传感器数据服务：调用模拟器生成数据并写入 sensor_data"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import config
from app.core.sensor_simulator import SensorSimulator
from app.models.device import DevicePoint
from app.models.monitor import SensorData

# 模拟器实例缓存：定时任务（无 seed）跨轮复用，保证状态连续（异常周期能正常累积触发）；
# 传入 seed 时新建实例，测试可复现。
_simulator: SensorSimulator | None = None


def _get_simulator(seed: int | None) -> SensorSimulator:
    """获取模拟器实例

    - seed 非空（测试/手动指定）：返回独立局部实例，不写回全局——
      避免 /api/simulator/run 带 seed 调用时重置定时任务的状态机
    - seed 为空（定时任务）：复用全局实例，状态跨轮连续（异常周期可累积）
    """
    global _simulator
    if seed is not None:
        return SensorSimulator(seed=seed)
    if _simulator is None:
        _simulator = SensorSimulator(seed=None)
    return _simulator


def list_active_points(db: Session) -> list[DevicePoint]:
    """查询所有启用的采集点位"""
    return list(db.scalars(select(DevicePoint).where(DevicePoint.enabled.is_(True))))


def list_recent_sensor_data(
    db: Session,
    device_id: int,
    point_id: int | None = None,
    limit: int = 200,
) -> list[dict]:
    """查询设备最近传感器数据，limit 表示"每个点位"最多返回多少条

    按点位分别取最近 limit 条（走 idx_point_time 索引），返回按点位分组、
    组内时间正序。这样温度/振动/电流各自都有完整的历史窗口，
    不会被多点位混合查询互相稀释。
    """
    point_stmt = select(DevicePoint).where(DevicePoint.device_id == device_id)
    if point_id is not None:
        point_stmt = point_stmt.where(DevicePoint.id == point_id)
    points = db.scalars(point_stmt).all()

    result: list[dict] = []
    for point in points:
        rows = db.scalars(
            select(SensorData)
            .where(SensorData.device_point_id == point.id)
            .order_by(SensorData.collected_at.desc())
            .limit(limit)
        ).all()
        for data in reversed(rows):  # 倒序查询 → 反转为时间正序
            result.append(
                {
                    "id": data.id,
                    "point_id": data.device_point_id,
                    "point_code": point.point_code,
                    "point_type": point.point_type,
                    "unit": point.unit,
                    "value": data.value,
                    "status": data.status,
                    "collected_at": data.collected_at.isoformat() if data.collected_at else None,
                }
            )
    return result


def generate_history(
    db: Session,
    minutes: int = 120,
    interval_seconds: int | None = None,
    seed: int | None = None,
) -> dict:
    """为所有启用点位生成最近 minutes 分钟的时序数据并入库

    Args:
        minutes: 回看分钟数（补历史数据，供趋势图/算法测试）
        interval_seconds: 采集间隔，默认取配置（60 秒）
        seed: 随机种子（测试可复现）

    Returns:
        {"points": 点位数量, "rows": 写入条数}
    """
    points = list_active_points(db)
    if not points:
        return {"points": 0, "rows": 0}

    interval = interval_seconds or config.simulate_interval_seconds
    simulator = _get_simulator(seed)
    now = datetime.now().replace(microsecond=0)
    total_steps = minutes * 60 // interval

    rows: list[SensorData] = []
    for point in points:
        # 每个点位独立推进状态机，生成连续序列
        for i in range(total_steps):
            collected_at = now - timedelta(seconds=(total_steps - 1 - i) * interval)
            sv = simulator.next_value(point)
            rows.append(
                SensorData(
                    device_id=point.device_id,
                    device_point_id=point.id,
                    value=sv.value,
                    status=sv.status,
                    collected_at=collected_at,
                )
            )

    db.add_all(rows)
    db.commit()
    return {"points": len(points), "rows": len(rows)}
