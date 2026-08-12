"""pytest 会话级配置

自动确保演示账号存在（test_notification 等集成测试依赖 admin/worker）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.user import SysUser  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def ensure_demo_users():
    """会话开始时确保 admin/worker 演示账号存在（幂等）"""
    db = SessionLocal()
    try:
        demo = [
            ("admin", "admin123", "系统管理员", "ADMIN"),
            ("worker", "worker123", "维修工-张伟", "MAINTENANCE_WORKER"),
            ("viewer", "viewer123", "观察者-李静", "VIEWER"),
        ]
        created = 0
        for username, password, real_name, role in demo:
            exists = db.scalar(select(SysUser.id).where(SysUser.username == username).limit(1))
            if exists is None:
                db.add(
                    SysUser(
                        username=username,
                        password_hash=hash_password(password),
                        real_name=real_name,
                        role=role,
                    )
                )
                created += 1
        db.commit()
        if created:
            print(f"[conftest] 创建演示账号 {created} 个")
    finally:
        db.close()
    yield
