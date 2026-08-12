"""模拟数据源执行脚本

用法（backend 目录下）：
    python scripts/run_simulator.py                # 补最近 120 分钟历史数据
    python scripts/run_simulator.py --minutes 360  # 补 6 小时
    python scripts/run_simulator.py --loop         # 持续模式，每分钟生成一轮
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.services import sensor_service  # noqa: E402


def run_once(minutes: int, seed: int | None) -> None:
    db = SessionLocal()
    try:
        result = sensor_service.generate_history(db, minutes=minutes, seed=seed)
        print(f"完成：{result['points']} 个点位，写入 {result['rows']} 条数据")
    finally:
        db.close()


def run_loop(interval_seconds: int) -> None:
    """持续模式：每轮为每个点位生成 1 条最新数据"""
    db = SessionLocal()
    try:
        print(f"持续模拟中（每 {interval_seconds} 秒一轮），Ctrl+C 停止...")
        while True:
            result = sensor_service.generate_history(
                db, minutes=interval_seconds // 60, interval_seconds=interval_seconds
            )
            print(f"[{time.strftime('%H:%M:%S')}] 写入 {result['rows']} 条")
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="仓脉智诊模拟数据源")
    parser.add_argument("--minutes", type=int, default=120, help="生成最近多少分钟（默认 120）")
    parser.add_argument("--loop", action="store_true", help="持续模式")
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    args = parser.parse_args()

    if args.loop:
        run_loop(60)
    else:
        run_once(args.minutes, args.seed)


if __name__ == "__main__":
    main()
