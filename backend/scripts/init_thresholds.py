"""初始化设备类型阈值模板

用法（backend 目录下）：python scripts/init_thresholds.py
阈值初值依据：ISO 10816 振动标准 + 轴承/电机温度经验值（详见 bootstrap_service）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.services.bootstrap_service import init_thresholds  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        count = init_thresholds(db)
        print(f"模板灌入完成，共 {count} 条")
    finally:
        db.close()


if __name__ == "__main__":
    main()
