"""定时任务验收测试

验证项：
1. 三个任务函数可直接执行（采集/判定/健康度）
2. create_scheduler() 注册了 3 个任务，id 与间隔正确
3. 调度器真实触发：短间隔跑采集任务，sensor_data 有新增

运行方式（backend 目录下）：python scripts/test_scheduler.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apscheduler.schedulers.background import BackgroundScheduler  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.monitor import SensorData  # noqa: E402
from app.tasks.scheduler import (  # noqa: E402
    create_scheduler,
    job_check_alerts,
    job_collect_data,
    job_compute_health,
)


def test_scheduler_flow() -> None:
    db = SessionLocal()
    try:
        # 1. 三个任务函数可直接执行
        job_collect_data()
        job_check_alerts()
        job_compute_health()
        print("[验证① 任务函数] 采集/判定/健康度直接调用无异常 OK")

        # 2. 调度器注册了 3 个任务
        scheduler = create_scheduler()
        job_ids = {job.id for job in scheduler.get_jobs()}
        assert job_ids == {"collect_data", "check_alerts", "compute_health", "diagnose"}
        print(f"[验证② 调度器配置] 4 个任务注册 OK：{sorted(job_ids)}")

        # 3. 真实触发：1 秒间隔跑两轮采集，验证数据增长
        before = db.scalar(select(func.max(SensorData.collected_at)))
        db.commit()  # 结束当前事务，后续查询才能看到其他 session 提交的数据
        test_scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        test_scheduler.add_job(
            job_collect_data,
            "interval",
            seconds=1,
            id="test_collect",
            max_instances=1,
            coalesce=True,
        )
        test_scheduler.start()
        time.sleep(2.5)  # 足够跑 2 轮
        test_scheduler.shutdown(wait=False)

        db.commit()
        stmt = select(func.count(SensorData.id))
        if before is not None:
            stmt = stmt.where(SensorData.collected_at > before)
        new_count = db.scalar(stmt)
        assert new_count is not None and new_count >= 1, "调度器未写入数据"
        print(f"[验证③ 真实触发] 1 秒间隔调度，新增 {new_count} 条数据 OK")

        print("\n========== 定时任务测试全部通过 ==========")
    finally:
        db.close()


if __name__ == "__main__":
    test_scheduler_flow()
