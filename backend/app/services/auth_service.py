"""认证服务：登录、当前用户解析"""

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, decode_token, verify_password
from app.database import get_db
from app.models.user import SysUser

bearer_scheme = HTTPBearer(auto_error=False)


def authenticate(db: Session, username: str, password: str) -> SysUser | None:
    """校验用户名密码，成功返回用户"""
    user = db.scalar(select(SysUser).where(SysUser.username == username).limit(1))
    if user is None or user.status != "ACTIVE":
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def login(db: Session, username: str, password: str) -> dict:
    """登录：成功返回 token + 用户信息，失败 401"""
    user = authenticate(db, username, password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user.id, user.role)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "role": user.role,
        },
    }


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> SysUser | None:
    """依赖注入：从 Bearer token 解析当前用户

    auth_enabled=False（联调期）时直接放行返回 None；
    打开后返回真实用户，token 非法抛 401。
    """
    if not config_auth_enabled():
        return None
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="未提供认证 token")
    try:
        payload = decode_token(credentials.credentials)
        user_id = int(payload.get("sub", "0"))
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(status_code=401, detail="token 无效或已过期") from None
    user = db.get(SysUser, user_id)
    if user is None or user.status != "ACTIVE":
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user


def config_auth_enabled() -> bool:
    """读取认证开关（延迟引用，便于测试切换）"""
    from app.config import config

    return config.auth_enabled


def list_users(db: Session) -> list[dict]:
    """用户列表（用于前端派单选择指派人，不含敏感字段）"""
    users = db.scalars(select(SysUser).where(SysUser.status == "ACTIVE").order_by(SysUser.id)).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "real_name": u.real_name,
            "role": u.role,
        }
        for u in users
    ]
