"""仓维云 FastAPI 入口

分层参考 OneCall 项目：main 只负责装配路由和生命周期，
业务逻辑全部在 services 层，路由只做参数校验与响应包装。

响应格式统一为 {"code": int, "message": str, "data": ...}：
- 业务成功：ok() 包装
- 业务失败：HTTPException → 由全局异常处理器统一包装
- 参数校验失败：422 → 统一包装
- 未捕获异常：500 → 统一包装（避免堆栈泄漏）
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app.api import (
    agent,
    alert,
    auth,
    device,
    fusion,
    health,
    kb,
    notification,
    overview,
    simulator,
    spare_part,
    warehouse,
    work_order,
)
from app.config import config
from app.tasks.scheduler import create_scheduler

# 认证开关打开时免认证的路径（文档 + 健康检查 + 登录）
PUBLIC_PATHS = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/auth/login",
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：启动/关闭钩子（后续挂定时任务用）"""
    print(f"{config.app_name} 启动中...")
    print(f"API 文档: http://{config.host}:{config.port}/docs")
    scheduler = create_scheduler()
    scheduler.start()
    print("定时任务已启动（采集/判定/健康度）")
    yield
    scheduler.shutdown(wait=False)
    print(f"{config.app_name} 关闭")


app = FastAPI(
    title=config.app_name,
    description="轻量化 AI 仓储设备智能维检平台 - 后端 API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发阶段放开，上线前收紧
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(warehouse.router)
app.include_router(device.router)
app.include_router(overview.router)
app.include_router(simulator.router)
app.include_router(alert.router)
app.include_router(health.router)
app.include_router(work_order.router)
app.include_router(spare_part.router)
app.include_router(auth.router)
app.include_router(notification.router)
app.include_router(agent.router)
app.include_router(kb.router)
app.include_router(fusion.router)


@app.middleware("http")
async def auth_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """认证拦截：auth_enabled=True 时除公开路径外全部需要 Bearer token"""
    if not config.auth_enabled or request.url.path in PUBLIC_PATHS:
        return await call_next(request)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"code": 401, "message": "未认证，请先登录", "data": None},
        )
    from app.core.security import decode_token

    try:
        decode_token(auth_header.removeprefix("Bearer "))
    except Exception:
        return JSONResponse(
            status_code=401,
            content={"code": 401, "message": "token 无效或已过期", "data": None},
        )
    return await call_next(request)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """业务异常统一包装：HTTPException → {code, message, data}"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": str(exc.detail),
            "data": None,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """参数校验失败统一包装：422 → {code, message, data}"""
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "参数校验失败",
            "data": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """未捕获异常：记录完整堆栈，对外只返回通用错误（防止泄漏内部信息）"""
    logger.exception(f"未捕获异常: {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "data": None,
        },
    )


@app.get("/health")
def health_check() -> dict:
    """健康检查"""
    return {"code": 200, "message": "success", "data": {"status": "healthy"}}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=config.host, port=config.port, reload=config.debug)
