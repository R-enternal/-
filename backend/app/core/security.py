"""安全工具：密码哈希 + JWT 生成/校验

- 密码：passlib bcrypt 哈希，不存明文
- JWT：HS256，payload 含 user_id(sub)、role、exp
"""

from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from app.config import config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """密码哈希"""
    return str(pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验密码"""
    return bool(pwd_context.verify(plain_password, hashed_password))


def create_access_token(user_id: int, role: str) -> str:
    """生成 JWT（角色写入 token，为后续鉴权做准备）"""
    expire = datetime.now(UTC) + timedelta(minutes=config.jwt_expire_minutes)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, config.jwt_secret_key, algorithm="HS256")


def decode_token(token: str) -> dict:
    """校验并解析 JWT，非法/过期抛 jwt.PyJWTError"""
    return jwt.decode(token, config.jwt_secret_key, algorithms=["HS256"])
