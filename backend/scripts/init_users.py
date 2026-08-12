"""初始化演示账号（幂等）

用法（backend 目录下）：python scripts/init_users.py
账号：admin/admin123（ADMIN）、worker/worker123（维修工）、viewer/viewer123（观察者）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.services.bootstrap_service import init_demo_users  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        created = init_demo_users(db)
        print(f"完成：新增 {created} 个账号（已存在则跳过）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
