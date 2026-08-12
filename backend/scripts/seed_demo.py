"""一条命令重建完整演示环境

用法（backend 目录下）：python scripts/seed_demo.py

流程：重置数据库 → 灌阈值模板 → 建演示账号 → 建仓库/设备/备件
      → 补 2 小时模拟数据 → 触发告警 + 健康度 → 转一条工单
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.services.bootstrap_service import (  # noqa: E402
    build_demo_data,
    init_demo_users,
    init_thresholds,
    reset_database,
)


def main() -> None:
    db = SessionLocal()
    try:
        print("1/5 重置数据库...")
        reset_database(db)
        print("2/5 灌入阈值模板...")
        tpl_count = init_thresholds(db)
        print("3/5 创建演示账号...")
        user_count = init_demo_users(db)
        print("4/5 构建演示数据（仓库/设备/备件/模拟数据/告警/健康度/工单）...")
        result = build_demo_data(db)
        print("5/5 完成")
        print(f"""
========== 演示环境就绪 ==========
阈值模板: {tpl_count} 条    演示账号: {user_count or 3} 个（admin/admin123）
仓库: {result['warehouses']}    设备: {result['devices']} 台（含点位）
备件: {result['parts']} 个    模拟数据: {result['sensor_rows']} 条
告警: {result['alerts']} 条    健康度记录: {result['health_records']} 条
工单: {result['work_orders']} 条
================================
""")
    finally:
        db.close()


if __name__ == "__main__":
    main()
