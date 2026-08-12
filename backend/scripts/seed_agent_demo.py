"""Agent 模块演示数据：初始化仓库忙闲时段表

用法（backend 目录下）：python scripts/seed_agent_demo.py
"""

import sys
from datetime import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.agent import MaintenanceBusyWindow  # noqa: E402
from app.models.warehouse import Warehouse  # noqa: E402

# 仓库每天三个时段：闲窗（凌晨作业）、早班、午班；工作日忙、周末闲
_WINDOWS = [
    (time(6, 0), time(8, 0), 1),  # 很闲（错峰首选）
    (time(8, 0), time(12, 0), 3),
    (time(13, 0), time(18, 0), 4),
]


def init_busy_windows(db) -> int:
    warehouses = db.scalars(select(Warehouse)).all()
    if not warehouses:
        print("没有仓库，跳过忙闲初始化")
        return 0
    existing = db.scalar(select(MaintenanceBusyWindow.id).limit(1))
    if existing is not None:
        print("忙闲时段表已有数据，跳过")
        return 0
    count = 0
    for wh in warehouses:
        for weekday in range(7):
            weekend = weekday >= 5
            for start, end, busy in _WINDOWS:
                level = 1 if busy == 1 else (2 if weekend else busy)
                db.add(
                    MaintenanceBusyWindow(
                        warehouse_id=wh.id,
                        weekday=weekday,
                        start_time=start,
                        end_time=end,
                        busy_level=level,
                    )
                )
                count += 1
    db.commit()
    return count


def main() -> None:
    db = SessionLocal()
    try:
        count = init_busy_windows(db)
        print(f"忙闲时段初始化完成：{count} 条")
    finally:
        db.close()


if __name__ == "__main__":
    main()
