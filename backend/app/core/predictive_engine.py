"""预测性告警引擎：Holt 双指数平滑（水平 + 趋势）外推未来，提前预警超限

定位：在"趋势已发生"的基础上，预测"即将超限"——
    PREDICTIVE 告警（快超限，提前处理）< TREND 告警（持续恶化）< THRESHOLD 告警（已超限）

算法（可解释）：
1. 对最近 window 条数据做 Holt 双指数平滑，得到当前水平 level 与趋势 trend
2. 预测未来 horizon 步：predicted = level + trend * horizon
3. 若 trend 指向阈值方向且预测值超限 → 触发 PREDICTIVE_HIGH / PREDICTIVE_LOW
4. 两道防误报门槛：当前水平已接近阈值（>= 50%）或预测超限幅度明显（>= 10%）
5. 输出预计到达阈值的时间（ETA），写进告警证据链
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PredictiveResult:
    """预测判定结果"""

    alert_type: str  # PREDICTIVE_HIGH / PREDICTIVE_LOW
    level: str  # WARNING
    metric_value: float  # 当前实际值（窗口最后值）
    predicted_value: float  # 预测值（未来 horizon 步）
    threshold: float  # 预测将超的阈值
    eta_steps: int  # 预计到达阈值所需步数
    trend: float  # 平滑后的趋势斜率


class HoltSmoother:
    """Holt 双指数平滑器（水平 + 趋势）"""

    def __init__(self, alpha: float = 0.5, beta: float = 0.3):
        self.alpha = alpha
        self.beta = beta

    def fit(self, values: Sequence[float]) -> tuple[float, float]:
        """对序列做平滑，返回 (最终水平 level, 最终趋势 trend)"""
        n = len(values)
        if n == 0:
            return 0.0, 0.0
        if n == 1:
            return values[0], 0.0

        level = values[0]
        trend = values[1] - values[0] if n >= 2 else 0.0
        for i in range(1, n):
            new_level = self.alpha * values[i] + (1 - self.alpha) * (level + trend)
            trend = self.beta * (new_level - level) + (1 - self.beta) * trend
            level = new_level
        return level, trend


def check_predictive(
    *,
    alarm_low: float | None,
    alarm_high: float | None,
    recent_values: Sequence[float],
    horizon: int = 12,
    window: int = 20,
    alpha: float = 0.5,
    beta: float = 0.3,
) -> PredictiveResult | None:
    """预测未来 horizon 步是否会超限，返回判定结果或 None

    防误报门槛：
    - 当前水平已到阈值的 50% 以上（level >= alarm_high * 0.5）
    - 或预测超限幅度 >= 阈值的 10%
    """
    if len(recent_values) < 5:
        return None
    window_values = (
        recent_values[-window:] if len(recent_values) >= window else list(recent_values)
    )

    level, trend = HoltSmoother(alpha=alpha, beta=beta).fit(window_values)
    latest = window_values[-1]
    predicted = level + trend * horizon

    if alarm_high is not None and trend > 0 and predicted >= alarm_high:
        if level >= alarm_high * 0.5 or (predicted - alarm_high) >= alarm_high * 0.1:
            eta = int((alarm_high - level) / trend) if trend > 0 else horizon
            return PredictiveResult(
                alert_type="PREDICTIVE_HIGH",
                level="WARNING",
                metric_value=latest,
                predicted_value=round(predicted, 2),
                threshold=alarm_high,
                eta_steps=max(eta, 1),
                trend=round(trend, 4),
            )

    if alarm_low is not None and trend < 0 and predicted <= alarm_low:
        if level <= alarm_low * 1.5 or (alarm_low - predicted) >= abs(alarm_low) * 0.1:
            eta = int((level - alarm_low) / abs(trend)) if trend < 0 else horizon
            return PredictiveResult(
                alert_type="PREDICTIVE_LOW",
                level="WARNING",
                metric_value=latest,
                predicted_value=round(predicted, 2),
                threshold=alarm_low,
                eta_steps=max(eta, 1),
                trend=round(trend, 4),
            )

    return None
