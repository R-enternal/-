"""模拟传感器数据生成器

模拟真实设备运行状态：
- 正常：围绕点位基线随机游走（基线由点位阈值推算，阈值的 55%~70%）
- 异常：周期性注入故障模式，按点位类型区分：
    TEMPERATURE 线性爬升（电机过热）、VIBRATION 阶梯加剧（轴承磨损）、
    CURRENT 大波动（负载异常），数值会突破阈值
- 支持固定随机种子，测试可复现
"""

import random
from dataclasses import dataclass
from typing import TypedDict

from app.models.device import DevicePoint


@dataclass
class SimulatedValue:
    value: float
    status: str = "NORMAL"


class PointState(TypedDict):
    """点位运行状态"""

    mode: str
    counter: int
    anomaly_remaining: int
    progress: float
    baseline: float | None


class SensorSimulator:
    """按点位生成时序数据，内部维护每个点位的运行状态机"""

    NORMAL_NOISE_RATIO = 0.05

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)
        self._states: dict[int, PointState] = {}

    def _state(self, point_id: int) -> PointState:
        """获取（或初始化）某个点位的运行状态"""
        if point_id not in self._states:
            self._states[point_id] = {
                "mode": "normal",  # normal / anomaly
                "counter": self._rng.randint(1, 50),  # 错开各点位触发时间
                "anomaly_remaining": 0,
                "progress": 0.0,
                "baseline": None,
            }
        return self._states[point_id]

    def _baseline(self, point: DevicePoint) -> float:
        """正常基线：由点位阈值推算，落在阈值区间的 55%~70%"""
        st = self._state(point.id)
        baseline = st["baseline"]
        if baseline is None:
            low, high = point.alarm_low, point.alarm_high
            if low is not None and high is not None:
                baseline = low + (high - low) * self._rng.uniform(0.55, 0.7)
            elif high is not None:
                baseline = high * self._rng.uniform(0.5, 0.65)
            elif low is not None:
                baseline = low * self._rng.uniform(1.1, 1.3)
            else:
                baseline = 1.0
            st["baseline"] = baseline
        return baseline

    def _anomaly_value(self, point: DevicePoint, baseline: float, st: PointState) -> float:
        """异常模式下的数值：按点位类型推进，最终突破阈值"""
        progress_ratio = st["progress"] / max(st["anomaly_remaining"] + st["progress"], 1)
        high = point.alarm_high
        if point.point_type == "TEMPERATURE" and high is not None:
            # 电机过热：从基线线性爬升到阈值上方 15%
            target = high * 1.15
            return baseline + (target - baseline) * progress_ratio + self._rng.gauss(0, 1.0)
        if point.point_type == "VIBRATION" and high is not None:
            # 轴承磨损：阶梯加剧 + 高频抖动
            step = int(progress_ratio * 8)
            base = high * (0.7 + 0.5 * progress_ratio)
            return base + step * 0.15 + self._rng.gauss(0, 0.3)
        # CURRENT：负载异常，大波动 + 上漂
        drift = high * 0.4 * progress_ratio if high is not None else baseline * 0.3 * progress_ratio
        return baseline + drift + self._rng.gauss(0, baseline * 0.2)

    def next_value(self, point: DevicePoint) -> SimulatedValue:
        """生成该点位下一个周期的数值"""
        st = self._state(point.id)
        baseline = self._baseline(point)
        st["counter"] += 1

        if st["mode"] == "normal":
            # 真实设备故障是小概率事件：正常 12~24 小时才进入一次异常（约 1~2 分钟）
            if st["counter"] >= self._rng.randint(720, 1440):
                # 进入异常期
                st["mode"] = "anomaly"
                st["anomaly_remaining"] = self._rng.randint(12, 20)
                st["progress"] = 0.0
            value = baseline * (1 + self._rng.gauss(0, self.NORMAL_NOISE_RATIO))
        else:
            st["anomaly_remaining"] -= 1
            st["progress"] += 1.0
            value = self._anomaly_value(point, baseline, st)
            if st["anomaly_remaining"] <= 0:
                # 异常结束，恢复正常，重置基线让后续状态独立
                st["mode"] = "normal"
                st["counter"] = 0
                st["baseline"] = None

        return SimulatedValue(value=round(max(value, 0.0), 3))
