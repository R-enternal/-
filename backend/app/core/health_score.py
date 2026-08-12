"""健康度评分模型

纯函数，不依赖数据库：
    点位分 = 100 − 阈值告警惩罚 − 趋势告警惩罚 − 稳定性惩罚 − 异常惩罚
    设备分 = 按点位类型权重的加权平均
    等级   = HEALTHY(>=90) / SUB_HEALTHY(70~89) / ABNORMAL(<70)
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

# 设备聚合权重（初始值：振动>温度>电流，后续可按设备类型调整）
POINT_TYPE_WEIGHTS: dict[str, float] = {
    "VIBRATION": 0.6,
    "TEMPERATURE": 0.3,
    "CURRENT": 0.1,
}
DEFAULT_WEIGHT = 0.1

# 扣分参数
ALERT_CRITICAL_PENALTY = 50.0  # 严重阈值告警
ALERT_WARNING_PENALTY = 30.0  # 普通阈值告警
TREND_ALERT_PENALTY = 20.0  # 趋势预警
PREDICTIVE_ALERT_PENALTY = 10.0  # 预测性预警（提前量，扣分最轻）
CV_THRESHOLD = 0.08  # 变异系数超过该值开始扣分
CV_MAX_PENALTY = 15.0
ANOMALY_THRESHOLD = 0.6  # 孤立森林异常分超过该值开始扣分
ANOMALY_MAX_PENALTY = 15.0


@dataclass
class PointScore:
    """点位健康度评分结果"""

    point_id: int
    point_type: str
    score: float
    deductions: dict[str, float] = field(default_factory=dict)  # 扣分原因 -> 扣分数
    anomaly_score: float = 0.0


def _coefficient_of_variation(values: Sequence[float]) -> float:
    """窗口内变异系数 CV = σ/μ（波动性指标）"""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance) / mean


def score_point(
    *,
    point_id: int,
    point_type: str,
    threshold_alert_level: str | None,
    has_trend_alert: bool,
    has_predictive_alert: bool,
    recent_values: Sequence[float],
    anomaly_score: float,
) -> PointScore:
    """给单个点位打分，返回评分与扣分明细（可解释）"""
    deductions: dict[str, float] = {}
    score = 100.0

    # 1. 阈值告警惩罚
    if threshold_alert_level:
        penalty = (
            ALERT_CRITICAL_PENALTY if threshold_alert_level == "CRITICAL" else ALERT_WARNING_PENALTY
        )
        deductions["threshold_alert"] = penalty
        score -= penalty

    # 2. 趋势告警惩罚
    if has_trend_alert:
        deductions["trend_alert"] = TREND_ALERT_PENALTY
        score -= TREND_ALERT_PENALTY

    # 3. 预测告警惩罚（提前量信号，最轻）
    if has_predictive_alert:
        deductions["predictive_alert"] = PREDICTIVE_ALERT_PENALTY
        score -= PREDICTIVE_ALERT_PENALTY

    # 4. 稳定性惩罚（波动过大扣分）
    cv = _coefficient_of_variation(recent_values)
    if cv > CV_THRESHOLD:
        cv_penalty = min(CV_MAX_PENALTY, (cv - CV_THRESHOLD) * 100)
        deductions["instability"] = round(cv_penalty, 2)
        score -= cv_penalty

    # 5. 孤立森林异常惩罚（辅助信号，封顶 15 分）
    if anomaly_score > ANOMALY_THRESHOLD:
        anomaly_penalty = min(
            ANOMALY_MAX_PENALTY,
            (anomaly_score - ANOMALY_THRESHOLD) * 37.5,
        )
        deductions["anomaly"] = round(anomaly_penalty, 2)
        score -= anomaly_penalty

    return PointScore(
        point_id=point_id,
        point_type=point_type,
        score=round(max(score, 0.0), 2),
        deductions=deductions,
        anomaly_score=round(anomaly_score, 4),
    )


def aggregate_device(point_scores: Sequence[PointScore]) -> float:
    """按点位类型权重聚合设备健康度"""
    total_weight = 0.0
    weighted_sum = 0.0
    for ps in point_scores:
        w = POINT_TYPE_WEIGHTS.get(ps.point_type, DEFAULT_WEIGHT)
        total_weight += w
        weighted_sum += w * ps.score
    if total_weight == 0:
        return 100.0
    return round(weighted_sum / total_weight, 2)


def level_of(score: float) -> str:
    """评分 → 等级"""
    if score >= 90:
        return "HEALTHY"
    if score >= 70:
        return "SUB_HEALTHY"
    return "ABNORMAL"
