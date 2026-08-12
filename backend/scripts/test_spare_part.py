"""备件与库存验收测试

验证项：
1. 备件创建（part_code 唯一）
2. 入库→出库：库存与流水一致
3. 超量出库被拒绝且库存/流水不变（事务回滚）
4. 低库存筛选、仓库过滤
5. 有流水记录的备件禁止删除

运行方式（backend 目录下）：python scripts/test_spare_part.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.spare_part import SparePart, StockRecord  # noqa: E402
from app.models.warehouse import Warehouse  # noqa: E402
from app.schemas.spare_part import SparePartCreate, StockChangeRequest  # noqa: E402
from app.services import spare_part_service  # noqa: E402


def test_spare_part_flow() -> None:
    db = SessionLocal()
    suffix = str(int(datetime.now().timestamp()))

    wh = Warehouse(name=f"备件测试仓-{suffix}")
    db.add(wh)
    db.commit()
    part_id: int | None = None

    try:
        # 1. 创建备件
        part = spare_part_service.create_spare_part(
            db,
            SparePartCreate(
                warehouse_id=wh.id,
                part_code=f"SP-{suffix}",
                name="输送带",
                spec="B500",
                safe_quantity=50,
                storage_location="A-01",
            ),
        )
        part_id = part.id
        assert part.stock_quantity == 0
        print(f"[验证① 创建] {part.part_code} 初始库存 0 OK")

        # 重复编号 → 400
        try:
            spare_part_service.create_spare_part(
                db, SparePartCreate(warehouse_id=wh.id, part_code=f"SP-{suffix}", name="重复")
            )
            raise AssertionError("重复 part_code 未被拒绝")
        except HTTPException as e:
            assert e.status_code == 400
        print("[验证② 编号唯一] 重复 part_code 400 OK")

        # 2. 入库 50
        part = spare_part_service.change_stock(
            db,
            part.id,
            StockChangeRequest(quantity=50, operator="张工", remark="首批采购"),
            "INBOUND",
        )
        assert part.stock_quantity == 50
        records = spare_part_service.list_stock_records(db, part.id)
        assert len(records) == 1
        r = records[0]
        assert r.change_type == "INBOUND" and r.quantity == 50 and r.balance_after == 50
        assert r.operator == "张工" and r.remark == "首批采购"
        print("[验证③ 入库] 库存 50，流水 INBOUND(+50,余量50) OK")

        # 3. 出库 30
        part = spare_part_service.change_stock(
            db, part.id, StockChangeRequest(quantity=30, operator="张工", remark="领用"), "OUTBOUND"
        )
        assert part.stock_quantity == 20
        records = spare_part_service.list_stock_records(db, part.id)
        assert len(records) == 2
        outbound = next(r for r in records if r.change_type == "OUTBOUND")
        assert outbound.quantity == -30 and outbound.balance_after == 20
        print("[验证④ 出库] 库存 20，流水 OUTBOUND(-30,余量20) OK")

        # 4. 超量出库 → 400，库存/流水不变
        try:
            spare_part_service.change_stock(
                db, part.id, StockChangeRequest(quantity=100), "OUTBOUND"
            )
            raise AssertionError("超量出库未被拒绝")
        except HTTPException as e:
            assert e.status_code == 400
        db.refresh(part)
        assert part.stock_quantity == 20, "超量出库后库存被修改"
        records = spare_part_service.list_stock_records(db, part.id)
        assert len(records) == 2, "超量出库后流水被新增"
        print("[验证⑤ 超量出库] 400 拒绝，库存 20 / 流水 2 条不变（回滚）OK")

        # 5. 低库存筛选（安全库存 50 > 当前 20）
        low = spare_part_service.list_spare_parts(db, warehouse_id=wh.id, low_stock=True)
        assert any(p.id == part.id for p in low)
        all_parts = spare_part_service.list_spare_parts(db, warehouse_id=wh.id)
        assert len(all_parts) == 1
        print("[验证⑥ 低库存筛选] 库存 20 < 安全库存 50，筛出 OK")

        # 6. 有流水禁止删除
        try:
            spare_part_service.delete_spare_part(db, part.id)
            raise AssertionError("有流水的备件被删除")
        except HTTPException as e:
            assert e.status_code == 400
        print("[验证⑦ 删除保护] 有流水记录不可删（建议 DISABLED）OK")

        print("\n========== 备件与库存测试全部通过 ==========")
    finally:
        db.rollback()
        if part_id is not None:
            db.query(StockRecord).filter(StockRecord.spare_part_id == part_id).delete()
            db.query(SparePart).filter(SparePart.id == part_id).delete()
        db.query(Warehouse).filter(Warehouse.id == wh.id).delete()
        db.commit()
        db.close()


if __name__ == "__main__":
    test_spare_part_flow()
