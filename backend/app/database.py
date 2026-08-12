"""数据库连接管理

SQLAlchemy 2.0 风格：声明式 Base + session 工厂 + 依赖注入。
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import config


class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""


engine = create_engine(
    config.mysql_url,
    pool_pre_ping=True,  # 每次取连接前先 ping，避免断连
    pool_recycle=3600,  # 1 小时回收连接
    echo=config.sql_echo,  # 默认关闭，需要调试 SQL 时在 .env 开启
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个 session，用完即关"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
