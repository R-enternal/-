"""仓脉智诊 Agent 工具集：把业务查询能力暴露给 LLM（工具 = Agent 的说明书）

每个工具直接调用现有 service/模型层，返回对 LLM 友好的文本。
description 是语义分流的关键：写清"什么时候用它"。
"""

from datetime import date

from langchain_core.tools import tool
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models.agent import MaintenanceBusyWindow
from app.models.device import Device
from app.models.fusion import FusionDiagnosis
from app.models.monitor import Alert, HealthRecord
from app.models.spare_part import SparePart
from app.models.work_order import WorkOrder
from app.tools.knowledge_tool import retrieve_knowledge


def _fmt(value: str | None) -> str:
    return value or "-"


@tool
def query_devices(status: str = "") -> str:
    """查询设备台账列表。当用户问"有哪些设备/几台设备/设备状态"时使用。

    Args:
        status: 设备状态过滤（RUNNING/STOPPED/MAINTENANCE/SCRAPPED），留空查全部
    """
    db = SessionLocal()
    try:
        stmt = select(Device).order_by(Device.id)
        if status:
            stmt = stmt.where(Device.status == status)
        devices = db.scalars(stmt).all()
        if not devices:
            return "当前没有设备。"
        lines = [
            f"{d.device_code} | {d.name} | 类型:{d.device_type} | 状态:{d.status} | 位置:{_fmt(d.location)}"
            for d in devices
        ]
        return "\n".join(lines)
    finally:
        db.close()


@tool
def query_device_health(device_name: str = "") -> str:
    """查询设备健康度（最新评分与等级）。当用户问"某台设备健康度/健康状态"时使用。

    Args:
        device_name: 设备名称关键字，留空查询全部设备
    """
    db = SessionLocal()
    try:
        latest = (
            select(HealthRecord.device_id, func.max(HealthRecord.computed_at).label("latest_at"))
            .group_by(HealthRecord.device_id)
            .subquery()
        )
        rows = db.execute(
            select(Device, HealthRecord.score, HealthRecord.level, HealthRecord.computed_at)
            .join(latest, latest.c.device_id == Device.id)
            .join(
                HealthRecord,
                (HealthRecord.device_id == latest.c.device_id)
                & (HealthRecord.computed_at == latest.c.latest_at),
            )
            .order_by(Device.id)
        ).all()
        if device_name:
            rows = [r for r in rows if device_name in r[0].name]
        if not rows:
            return "未查询到健康度数据（健康度每 5 分钟计算一次，请稍后再试）。"
        lines = [
            f"{d.name} | 健康度:{score:.1f} | 等级:{level} | 计算时间:{computed_at}"
            for d, score, level, computed_at in rows
        ]
        return "\n".join(lines)
    finally:
        db.close()


@tool
def query_alerts(status: str = "PENDING") -> str:
    """查询告警记录。当用户问"有哪些告警/待处理告警/报警"时使用。

    Args:
        status: 告警状态（PENDING/HANDLED/IGNORED/CONVERTED），默认待处理
    """
    db = SessionLocal()
    try:
        stmt = (
            select(Alert, Device.name)
            .join(Device, Device.id == Alert.device_id)
            .order_by(Alert.created_at.desc())
            .limit(20)
        )
        if status:
            stmt = stmt.where(Alert.status == status)
        rows = db.execute(stmt).all()
        if not rows:
            return f"没有{status or '任何'}告警记录。"
        lines = []
        for alert, device_name in rows:
            lines.append(
                f"{alert.created_at:%m-%d %H:%M} | {device_name} | {alert.alert_type} | "
                f"级别:{alert.level} | 状态:{alert.status} | {alert.title}"
            )
        return "\n".join(lines)
    finally:
        db.close()


@tool
def query_work_orders(status: str = "") -> str:
    """查询工单列表。当用户问"有哪些工单/待派单/进行中的工单"时使用。

    Args:
        status: 工单状态（PENDING_ASSIGN/PENDING_EXECUTE/IN_PROGRESS/PENDING_ACCEPT/COMPLETED/CANCELLED），留空查全部
    """
    db = SessionLocal()
    try:
        stmt = (
            select(WorkOrder, Device.name)
            .join(Device, Device.id == WorkOrder.device_id)
            .order_by(WorkOrder.created_at.desc())
            .limit(20)
        )
        if status:
            stmt = stmt.where(WorkOrder.status == status)
        rows = db.execute(stmt).all()
        if not rows:
            return f"没有{status or '任何'}工单。"
        lines = []
        for order, device_name in rows:
            lines.append(
                f"{order.order_no} | {device_name} | {order.title} | 优先级:{order.priority} | 状态:{order.status}"
            )
        return "\n".join(lines)
    finally:
        db.close()


@tool
def query_spare_parts(low_stock_only: bool = False) -> str:
    """查询备件库存。当用户问"备件/库存/低库存备件"时使用。

    Args:
        low_stock_only: 是否只看低库存备件
    """
    db = SessionLocal()
    try:
        parts = db.scalars(select(SparePart).order_by(SparePart.id)).all()
        if low_stock_only:
            parts = [
                p for p in parts if p.safe_quantity > 0 and p.stock_quantity < p.safe_quantity
            ]
        if not parts:
            return "没有符合条件的备件。"
        lines = [
            f"{p.part_code} | {p.name} | 库存:{p.stock_quantity} | 安全库存:{p.safe_quantity} | 库位:{_fmt(p.storage_location)}"
            for p in parts
        ]
        return "\n".join(lines)
    finally:
        db.close()


@tool
def get_busy_window(weekday: int | None = None) -> str:
    """查询仓库忙闲时段（1=很闲，5=很忙），用于错峰安排维保。

    Args:
        weekday: 星期 0-6（周一=0），留空按今天
    """
    if weekday is None:
        weekday = date.today().weekday()
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(MaintenanceBusyWindow)
                .where(MaintenanceBusyWindow.weekday == weekday)
                .order_by(MaintenanceBusyWindow.busy_level)
            )
            .scalars()
            .all()
        )
        if not rows:
            return f"星期{weekday}暂无忙闲数据，请先初始化忙闲时段表。"
        lines = [f"时段 {w.start_time:%H:%M}-{w.end_time:%H:%M} | 忙闲等级:{w.busy_level}" for w in rows]
        return f"星期{weekday}的忙闲时段（越小越闲）：\n" + "\n".join(lines)
    finally:
        db.close()


@tool
def query_device_diagnosis(device_name: str = "") -> str:
    """查询设备融合诊断结果（故障模式与置信度）。

    当用户问"某台设备是什么故障/哪里坏了/诊断结果"时使用。

    Args:
        device_name: 设备名称关键字，留空查询全部设备最近诊断
    """
    db = SessionLocal()
    try:
        rows = db.execute(
            select(FusionDiagnosis, Device.name)
            .join(Device, Device.id == FusionDiagnosis.device_id)
            .order_by(FusionDiagnosis.created_at.desc())
            .limit(20)
        ).all()
        if device_name:
            rows = [r for r in rows if device_name in r[1]]
        if not rows:
            return "暂无融合诊断记录（定时任务每 5 分钟诊断一次）。"
        type_text = {
            "NORMAL": "正常",
            "BEARING_WEAR": "轴承磨损",
            "MOTOR_OVERHEAT": "电机过热",
            "LOAD_ABNORMAL": "负载异常",
            "COMPOSITE_FAULT": "复合故障",
        }
        lines = []
        for diag, device_name in rows:
            signals = (diag.signals_json or {}).get("signals", [])
            evidence = "; ".join(
                f"{s['name']}:{s['evidence']}" for s in signals if s["severity"] != "NONE"
            )
            lines.append(
                f"{device_name} | 诊断:{type_text.get(diag.fault_type, diag.fault_type)} | "
                f"置信度:{diag.confidence:.0%} | 证据:{evidence or '正常'}"
            )
        return "\n".join(lines)
    finally:
        db.close()


ALL_AGENT_TOOLS = [
    query_devices,
    query_device_health,
    query_alerts,
    query_work_orders,
    query_spare_parts,
    get_busy_window,
    retrieve_knowledge,
    query_device_diagnosis,
]
