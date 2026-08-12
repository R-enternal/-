"""多传感器融合诊断引擎

把振动 / 温度 / 电流三路信号联合判定，从"知道异常"升级到"知道哪坏了、为什么坏"。

可解释规则：
1. 每个信号单独分析 → 严重度 + 证据（超限 / 趋势爬升 / 波动过大）
2. 融合判定：
   - 无异常信号              → NORMAL
   - 仅振动异常              → BEARING_WEAR（轴承磨损）
   - 仅温度异常              → MOTOR_OVERHEAT（电机过热）
   - 仅电流异常              → LOAD_ABNORMAL（负载异常）
   - 多个信号同时异常          → COMPOSITE_FAULT（复合故障）
3. 置信度由异常信号个数与严重度决定，输出处置建议（对应维保手册）
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

# 信号异常判定参数
TREND_WINDOW = 10  # 趋势/波动分析窗口（采样点数）
TREND_RISE_RATIO = 0.03  # 窗口上升幅度 >= 阈值 3% 视为趋势上升
CV_HIGH = 0.12  # 变异系数超过该值视为波动过大

# 故障模式
NORMAL = "NORMAL"
BEARING_WEAR = "BEARING_WEAR"
MOTOR_OVERHEAT = "MOTOR_OVERHEAT"
LOAD_ABNORMAL = "LOAD_ABNORMAL"
COMPOSITE_FAULT = "COMPOSITE_FAULT"

# 处置建议（与维保手册对应）
RECOMMENDATIONS: dict[str, str] = {
    NORMAL: "设备运行正常，按计划巡检即可。",
    BEARING_WEAR: "检查轴承润滑与磨损情况，必要时更换轴承；同时检查传动链张紧度。",
    MOTOR_OVERHEAT: "清理散热风扇与散热片，检查负载是否过重，测量三相电流是否平衡。",
    LOAD_ABNORMAL: "排查卡料/堵包等负载障碍，检查电压稳定性和变频器参数。",
    COMPOSITE_FAULT: "存在多个异常信号，建议立即停机综合检修，优先处理严重信号。",
}


@dataclass
class SignalFeature:
    """单信号诊断证据"""

    name: str  # VIBRATION / TEMPERATURE / CURRENT
    value: float
    threshold: float | None
    ratio: float | None  # 当前值 / 阈值
    trend_rise: float  # 窗口上升幅度（阈值比例）
    cv: float  # 变异系数
    severity: str = "NONE"  # NONE / LOW / MEDIUM / HIGH
    evidence: str = ""


@dataclass
class DiagnosisResult:
    """融合诊断结果"""

    fault_type: str
    confidence: float
    signals: list[SignalFeature] = field(default_factory=list)
    recommendation: str = ""


def _linear_slope(values: Sequence[float]) -> float:
    """最小二乘斜率"""
    n = len(values)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    numerator = sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values))
    denominator = sum((i - mean_x) ** 2 for i in range(n))
    return numerator / denominator if denominator else 0.0


def _cv(values: Sequence[float]) -> float:
    """变异系数 σ/μ"""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance) / mean


def analyze_signal(name: str, values: Sequence[float], alarm_high: float | None) -> SignalFeature:
    """分析单个信号：超限 / 趋势 / 波动 → 严重度"""
    if not values:
        return SignalFeature(name=name, value=0.0, threshold=alarm_high, ratio=None, trend_rise=0.0, cv=0.0)
    window = list(values[-TREND_WINDOW:]) if len(values) >= TREND_WINDOW else list(values)
    latest = window[-1]
    ratio = latest / alarm_high if alarm_high and alarm_high > 0 else None

    slope = _linear_slope(window)
    trend_rise = (slope * (len(window) - 1)) / alarm_high if alarm_high and alarm_high > 0 else 0.0
    cv = _cv(window)

    over_limit = alarm_high is not None and latest > alarm_high
    rising = trend_rise >= TREND_RISE_RATIO
    unstable = cv > CV_HIGH

    # 严重度与证据（可解释）
    if over_limit:
        severity = "HIGH"
        evidence = f"当前值 {latest:.2f} 已超上限 {alarm_high}"
    elif rising:
        severity = "MEDIUM"
        evidence = f"窗口上升幅度达阈值 {trend_rise:.1%}"
    elif unstable:
        severity = "LOW"
        evidence = f"波动较大（变异系数 {cv:.2f}）"
    else:
        severity = "NONE"
        evidence = "信号正常"

    return SignalFeature(
        name=name,
        value=latest,
        threshold=alarm_high,
        ratio=round(ratio, 3) if ratio is not None else None,
        trend_rise=round(trend_rise, 4),
        cv=round(cv, 4),
        severity=severity,
        evidence=evidence,
    )


def _severity_score(sev: str) -> int:
    return {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}[sev]


def _confidence_of(sev: str) -> float:
    return {"LOW": 0.6, "MEDIUM": 0.75, "HIGH": 0.9}[sev]


def diagnose(
    *,
    vibration_values: Sequence[float],
    temperature_values: Sequence[float],
    current_values: Sequence[float],
    vibration_high: float | None,
    temperature_high: float | None,
    current_high: float | None,
) -> DiagnosisResult:
    """三路信号融合诊断"""
    signals = [
        analyze_signal("VIBRATION", vibration_values, vibration_high),
        analyze_signal("TEMPERATURE", temperature_values, temperature_high),
        analyze_signal("CURRENT", current_values, current_high),
    ]
    abnormal = [s for s in signals if s.severity != "NONE"]

    if not abnormal:
        return DiagnosisResult(
            fault_type=NORMAL,
            confidence=0.98,
            signals=signals,
            recommendation=RECOMMENDATIONS[NORMAL],
        )

    # 复合故障：多个信号异常
    if len(abnormal) >= 2:
        confidence = min(0.85 + 0.05 * len(abnormal), 0.95)
        return DiagnosisResult(
            fault_type=COMPOSITE_FAULT,
            confidence=confidence,
            signals=signals,
            recommendation=RECOMMENDATIONS[COMPOSITE_FAULT],
        )

    # 单信号故障：按信号类型定故障模式
    signal = abnormal[0]
    fault_map = {
        "VIBRATION": BEARING_WEAR,
        "TEMPERATURE": MOTOR_OVERHEAT,
        "CURRENT": LOAD_ABNORMAL,
    }
    fault_type = fault_map.get(signal.name, COMPOSITE_FAULT)
    return DiagnosisResult(
        fault_type=fault_type,
        confidence=_confidence_of(signal.severity),
        signals=signals,
        recommendation=RECOMMENDATIONS.get(fault_type, ""),
    )
