"""技术验证实验：融合诊断准确率 + 预测性预警提前量（企划书数据支撑）

实验一：构造 5 类故障场景（正常/轴承磨损/电机过热/负载异常/复合故障），
        每类 30 组带噪声样本，统计融合诊断总体准确率与各类准确率。
实验二：构造温度爬升序列（每分钟一条，60s 间隔），统计"预测性预警"
        比"阈值告警"平均提前多少个采样周期（分钟）。
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import fusion_engine  # noqa: E402
from app.core.predictive_engine import check_predictive  # noqa: E402
from app.core.threshold_engine import check_threshold  # noqa: E402

# 阈值（与阈值模板一致）
V_HIGH, T_HIGH, C_HIGH = 7.1, 85.0, 50.0


def gen_normal(n: int = 30, base: float = 3.0) -> list[float]:
    return [base + random.gauss(0, base * 0.05) for _ in range(n)]


def gen_vibration_fault(n: int = 30) -> list[float]:
    return [3.0 + i * 0.35 + random.gauss(0, 0.25) for i in range(n)]


def gen_temp_fault(n: int = 30) -> list[float]:
    return [50.0 + i * 1.6 + random.gauss(0, 0.6) for i in range(n)]


def gen_current_fault(n: int = 30) -> list[float]:
    return [28.0 + (i % 4) * 7.0 + random.gauss(0, 1.0) for i in range(n)]


def diagnose_case(v, t, c):
    return fusion_engine.diagnose(
        vibration_values=v,
        temperature_values=t,
        current_values=c,
        vibration_high=V_HIGH,
        temperature_high=T_HIGH,
        current_high=C_HIGH,
    ).fault_type


def experiment_fusion() -> None:
    cases = [
        ("BEARING_WEAR", gen_vibration_fault, gen_normal, gen_normal),
        ("MOTOR_OVERHEAT", gen_normal, gen_temp_fault, gen_normal),
        ("LOAD_ABNORMAL", gen_normal, gen_normal, gen_current_fault),
        ("COMPOSITE_FAULT", gen_vibration_fault, gen_temp_fault, gen_normal),
        ("NORMAL", gen_normal, gen_normal, gen_normal),
    ]
    total = correct = 0
    per_class = {}
    for fault, gv, gt, gc in cases:
        c = ok = 0
        for _ in range(30):
            pred = diagnose_case(gv(), gt(), gc())
            c += 1
            total += 1
            if pred == fault:
                ok += 1
                correct += 1
        per_class[fault] = (ok, c)
        print(f"  {fault}: {ok}/{c} = {ok / c:.1%}")
    print(f"  总体准确率: {correct}/{total} = {correct / total:.1%}")


def experiment_predictive() -> None:
    """温度从 45~55 随机基线爬升，上限 85；统计预测告警比阈值告警提前几步"""
    lead_times = []
    for _ in range(30):
        base = random.uniform(45, 55)
        slope = random.uniform(0.6, 1.6)  # 每分钟爬升幅度
        values = []
        threshold_step = None
        predict_step = None
        step = 0
        while threshold_step is None and step < 300:
            values.append(base + step * slope + random.gauss(0, 0.4))
            if len(values) >= 3:
                thr = check_threshold(
                    alarm_low=None, alarm_high=T_HIGH, recent_values=values, debounce_count=3
                )
                if thr is not None and threshold_step is None:
                    threshold_step = step
            if predict_step is None:
                pred = check_predictive(
                    alarm_low=None,
                    alarm_high=T_HIGH,
                    recent_values=values,
                    horizon=12,
                    window=20,
                )
                if pred is not None:
                    predict_step = step
            step += 1
        if threshold_step is not None and predict_step is not None:
            lead_times.append(threshold_step - predict_step)
    if lead_times:
        avg = sum(lead_times) / len(lead_times)
        print(f"  有效样本 {len(lead_times)} 组，平均提前 {avg:.1f} 分钟，最小 {min(lead_times)}，最大 {max(lead_times)}")
    else:
        print("  无有效样本")


def main() -> None:
    random.seed(42)
    print("[实验一] 融合诊断准确率（每类 30 组带噪声样本）")
    experiment_fusion()
    print("\n[实验二] 预测性预警提前量（vs 阈值告警，60s/采样）")
    experiment_predictive()


if __name__ == "__main__":
    main()
