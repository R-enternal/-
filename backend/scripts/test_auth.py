"""认证模块验收测试

验证项：
1. 密码哈希/校验（不存明文）
2. 登录成功返回 token（含角色）/ 密码错误 401
3. auth_enabled=True：不带 token 401，带 token 200，公开路径免认证
4. auth_enabled=False：所有接口免认证（联调期默认）

运行方式（backend 目录下）：python scripts/test_auth.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import config  # noqa: E402
from app.core.security import (  # noqa: E402
    decode_token,
    hash_password,
    verify_password,
)
from app.database import SessionLocal  # noqa: E402
from app.models.user import SysUser  # noqa: E402
from app.services import auth_service  # noqa: E402


def test_auth_flow() -> None:
    db = SessionLocal()
    suffix = str(int(datetime.now().timestamp()))
    username = f"auth_test_{suffix}"
    test_user_id: int | None = None
    original_auth_enabled = config.auth_enabled

    try:
        # 1. 密码哈希/校验
        hashed = hash_password("secret123")
        assert hashed != "secret123" and hashed.startswith("$2")
        assert verify_password("secret123", hashed)
        assert not verify_password("wrong", hashed)
        print("[验证① 密码哈希] 不存明文，校验正确/错误 OK")

        # 2. 建测试用户 + 登录
        user = SysUser(
            username=username,
            password_hash=hash_password("pass123"),
            real_name="测试用户",
            role="ADMIN",
        )
        db.add(user)
        db.commit()
        test_user_id = user.id

        result = auth_service.login(db, username, "pass123")
        assert result["token"] and result["user"]["role"] == "ADMIN"
        payload = decode_token(result["token"])
        assert payload["sub"] == str(user.id) and payload["role"] == "ADMIN"
        print("[验证② 登录] 正确密码拿 token（含角色）OK")

        try:
            auth_service.login(db, username, "wrong")
            raise AssertionError("错误密码登录成功")
        except Exception as e:
            assert getattr(e, "status_code", None) == 401
        print("[验证③ 错误密码] 401 OK")

        # 3. 中间件集成：开启认证
        from app.main import app

        client = TestClient(app)
        config.auth_enabled = True

        r = client.get("/api/devices")
        assert r.status_code == 401, f"未带 token 应 401，实际 {r.status_code}"
        print("[验证④ 开关开启] 未带 token → 401 OK")

        r = client.get("/health")
        assert r.status_code == 200
        r = client.post(
            "/api/auth/login",
            json={"username": username, "password": "pass123"},
        )
        assert r.status_code == 200
        token = r.json()["data"]["token"]
        r = client.get("/api/devices", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, f"带 token 应 200，实际 {r.status_code}"
        print("[验证⑤ 开关开启] 公开路径免认证 + 带 token 200 OK")

        # 4. 关闭认证：免认证
        config.auth_enabled = False
        r = client.get("/api/devices")
        assert r.status_code == 200, f"开关关闭应放行，实际 {r.status_code}"
        print("[验证⑥ 开关关闭] 所有接口免认证 OK")

        print("\n========== 认证测试全部通过 ==========")
    finally:
        config.auth_enabled = original_auth_enabled
        db.rollback()
        if test_user_id is not None:
            db.query(SysUser).filter(SysUser.id == test_user_id).delete()
            db.commit()
        db.close()


if __name__ == "__main__":
    test_auth_flow()
