"""通用响应包装

统一响应格式（参考 OneCall 的 ApiResponse）：
{"code": 200, "message": "success", "data": {...}}
"""

from typing import Any

from pydantic import BaseModel


class ApiResponse[T](BaseModel):
    code: int = 200
    message: str = "success"
    data: T | None = None


def ok(data: Any = None, message: str = "success") -> dict:
    """成功响应"""
    return {"code": 200, "message": message, "data": data}
