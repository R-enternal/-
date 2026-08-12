"""APScheduler 定时任务

三个任务串联监测闭环（模拟开发阶段，无真实网关数据）：
    1. collect_data  每 60 秒   生成一轮最新传感器数据
    2. check_alerts  每 3 分钟  阈值 + 趋势双判定（防抖需 3 条数据）
    3. compute_health 每 5 分钟 健康度评分写入 health_record

所有任务 max_instances=1 + coalesce=True，防止任务积压重叠。
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.config import config
from app.database import SessionLocal
from app.services import alert_service, fusion_service, health_service, sensor_service


def job_collect_data() -> None:
    """模拟采集：每个启用点位生成 1 条最新数据"""
    db = SessionLocal()
    try:
        result = sensor_service.generate_history(
            db, minutes=1, interval_seconds=config.simulate_interval_seconds
        )
        logger.info(f"[定时] 采集完成：{result['rows']} 条")
    except Exception:
        logger.exception("[定时] 采集任务失败")
    finally:
        db.close()


def job_check_alerts() -> None:
    """阈值 + 趋势双判定"""
    db = SessionLocal()
    try:
        result = alert_service.check_all_points(db)
        logger.info(f"[定时] 判定完成：检查 {result['points']} 点位，新增 {result['created']} 告警")
    except Exception:
        logger.exception("[定时] 判定任务失败")
    finally:
        db.close()


def job_compute_health() -> None:
    """健康度评分"""
    db = SessionLocal()
    try:
        result = health_service.compute_all_health(db)
        logger.info(f"[定时] 健康度完成：{result['devices']} 台设备")
    except Exception:
        logger.exception("[定时] 健康度任务失败")
    finally:
        db.close()


def job_diagnose() -> None:
    """融合诊断：每 5 分钟对全部运行设备做多传感器联合诊断"""
    db = SessionLocal()
    try:
        result = fusion_service.diagnose_all(db)
        logger.info(f"[定时] 诊断完成：{result['devices']} 台设备")
    except Exception:
        logger.exception("[定时] 诊断任务失败")
    finally:
        db.close()


def create_scheduler() -> BackgroundScheduler:
    """创建并注册三个定时任务"""
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    scheduler.add_job(
        job_collect_data,
        IntervalTrigger(seconds=config.simulate_interval_seconds),
        id="collect_data",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
    )
    scheduler.add_job(
        job_check_alerts,
        IntervalTrigger(minutes=3),
        id="check_alerts",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        job_compute_health,
        IntervalTrigger(minutes=5),
        id="compute_health",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        job_diagnose,
        IntervalTrigger(minutes=5),
        id="diagnose",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    return scheduler
