"""趋势层判定引擎

纯函数，不依赖数据库。基于滑动窗口（多数据点）做最小二乘线性回归，
判定"持续上升趋势"，与阈值告警（看单点绝对值）相互独立。

规则（可解释）：
    - 取最近 trend_window 条数据（最少 MIN_WINDOW 条）
    - 计算窗口上升幅度 rise = 最后值 - 起始值
    - 计算线性回归斜率 slope（正数表示持续上升）
    - rise >= trend_delta 且 slope > 0 → 触发 TREND 告警
"""

from collections.abc import Sequence
from dataclasses import dataclass

# 最少需要的数据点数，少于它无法判断趋势
MIN_WINDOW = 5


@dataclass(frozen=True)
class TrendResult:
    """趋势判定结果"""

    alert_type: str  # TREND
    level: str  # WARNING
    metric_value: float  # 窗口最后值（当前值）
    threshold: float  # trend_delta（上升幅度阈值）
    slope: float  # 线性回归斜率
    rise_amount: float  # 窗口上升幅度


def _linear_slope(values: Sequence[float]) -> float:
    """最小二乘线性回归斜率（x 为等间隔索引 0..n-1）"""
    n = len(values)
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    numerator = sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values))
    denominator = sum((i - mean_x) ** 2 for i in range(n))
    return numerator / denominator if denominator else 0.0


def check_trend(
    *,
    recent_values: Sequence[float],
    trend_delta: float,
    trend_window: int,
) -> TrendResult | None:
    """基于滑动窗口判断持续上升趋势，无趋势返回 None

    Args:
        recent_values: 最近采集值序列（时间升序）
        trend_delta: 窗口上升幅度阈值（点位可配）
        trend_window: 滑动窗口大小（采样点数，点位可配）
    """
    if len(recent_values) < MIN_WINDOW:
        return None

    # 取最近 trend_window 条作为窗口（数据不足则用全部可用数据）
    window = recent_values[-trend_window:] if len(recent_values) >= trend_window else recent_values
    if len(window) < MIN_WINDOW:
        return None

    rise = window[-1] - window[0]
    slope = _linear_slope(window)

    if rise >= trend_delta and slope > 0:
        return TrendResult(
            alert_type="TREND",
            level="WARNING",
            metric_value=window[-1],
            threshold=trend_delta,
            slope=round(slope, 4),
            rise_amount=round(rise, 3),
        )
    return None
