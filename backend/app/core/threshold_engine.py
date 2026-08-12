"""阈值层判定引擎

纯函数，不依赖数据库，输入"点位阈值 + 最近数据序列"，输出判定结果。
规则（可解释）：
    - 最近 N 条（默认 3）全部超过上限 → THRESHOLD_HIGH
    - 最近 N 条全部低于下限     → THRESHOLD_LOW
    - 超限幅度 > 20% 视为 CRITICAL，否则 WARNING
    - 数据不足 N 条或未连续超限 → 不告警（防抖）
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ThresholdResult:
    """阈值判定结果"""

    alert_type: str  # THRESHOLD_HIGH / THRESHOLD_LOW
    level: str  # WARNING / CRITICAL
    metric_value: float  # 触发时的实际值（窗口内最新值）
    threshold: float  # 触发的阈值


def check_threshold(
    *,
    alarm_low: float | None,
    alarm_high: float | None,
    recent_values: Sequence[float],
    debounce_count: int = 3,
) -> ThresholdResult | None:
    """连续 debounce_count 次超限才返回告警结果，否则返回 None

    Args:
        alarm_low: 点位报警下限（可空）
        alarm_high: 点位报警上限（可空）
        recent_values: 最近采集值序列（时间升序，仅需最后 N 条）
        debounce_count: 防抖次数，默认 3
    """
    if len(recent_values) < debounce_count:
        # 数据不足，无法满足"连续 N 次"条件
        return None

    # 只看最近 N 条，确保"连续"
    window = recent_values[-debounce_count:]
    latest = window[-1]

    if alarm_high is not None and all(v > alarm_high for v in window):
        level = "CRITICAL" if latest > alarm_high * 1.2 else "WARNING"
        return ThresholdResult(
            alert_type="THRESHOLD_HIGH",
            level=level,
            metric_value=latest,
            threshold=alarm_high,
        )

    if alarm_low is not None and all(v < alarm_low for v in window):
        level = "CRITICAL" if latest < alarm_low * 0.8 else "WARNING"
        return ThresholdResult(
            alert_type="THRESHOLD_LOW",
            level=level,
            metric_value=latest,
            threshold=alarm_low,
        )

    return None
