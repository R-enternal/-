"""认证路由"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import ok
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["认证"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)) -> dict:
    """登录：返回 JWT（含角色）"""
    result = auth_service.login(db, data.username, data.password)
    return ok(data=result, message="登录成功")


@router.get("/users")
def list_users(db: Session = Depends(get_db)) -> dict:
    """用户列表（派单选择指派人用）"""
    return ok(data=auth_service.list_users(db))
