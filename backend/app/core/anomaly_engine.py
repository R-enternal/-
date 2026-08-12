"""孤立森林异常检测引擎

定位（与企划书一致）：作为健康度评分的"辅助信号"，不直接触发告警。
- 训练：用点位历史数据（>= MIN_SAMPLES 条）训练 IsolationForest
- 推理：对最新值输出异常分 s ∈ [0, 1]，越接近 1 越异常
- 模型按 point_id 缓存，训练数据量变化时自动重训

异常分计算：score_samples 返回负对数平均路径长度（越负越异常），
将其在训练集的最小/最大值之间线性映射到 [0, 1]。
"""

import numpy as np
from sklearn.ensemble import IsolationForest

MIN_SAMPLES = 100  # 训练所需最少样本数（冷启动保护）
MAX_SAMPLES = 500  # 训练样本上限（防止历史无限增长拖慢训练）


class IsolationForestEngine:
    """单点位孤立森林（一个引擎实例对应一个点位）"""

    def __init__(
        self, n_estimators: int = 100, contamination: float = 0.05, seed: int | None = None
    ):
        self._model: IsolationForest | None = None
        self._raw_min: float = -1.0
        self._raw_max: float = 0.0
        self._trained_on: int = 0  # 训练时的样本数
        self._n_estimators = n_estimators
        self._contamination = contamination
        self._seed = seed

    def fit(self, values: list[float]) -> None:
        """用历史数据训练（数据不足或未增长时跳过）"""
        if len(values) < MIN_SAMPLES or len(values) <= self._trained_on:
            return
        samples = values[-MAX_SAMPLES:]
        X = np.asarray(samples, dtype=float).reshape(-1, 1)
        self._model = IsolationForest(
            n_estimators=self._n_estimators,
            contamination=self._contamination,
            random_state=self._seed,
        )
        self._model.fit(X)
        # 记录训练集的 score_samples 边界，用于归一化
        raws = self._model.score_samples(X)
        self._raw_min, self._raw_max = float(raws.min()), float(raws.max())
        self._trained_on = len(samples)

    def anomaly_score(self, value: float) -> float:
        """对最新值输出异常分 s ∈ [0, 1]（未训练时返回 0，即不惩罚）"""
        if self._model is None:
            return 0.0
        raw = float(self._model.score_samples(np.asarray([[value]], dtype=float))[0])
        # 线性映射：raw_min（最异常）→ 1，raw_max（最正常）→ 0
        if self._raw_max - self._raw_min < 1e-9:
            return 0.0
        s = (raw - self._raw_max) / (self._raw_min - self._raw_max)
        return float(np.clip(s, 0.0, 1.0))

    @property
    def is_trained(self) -> bool:
        return self._model is not None
