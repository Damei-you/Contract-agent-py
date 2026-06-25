"""数据库 Session 管理。

当前阶段采用同步 SQLAlchemy，便于先完成业务闭环；如果后续切到 asyncpg/AsyncSession，
只需要替换本模块和仓储实现。
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def create_database_engine(database_url: str | None = None) -> Engine:
    """创建 SQLAlchemy Engine。

    测试使用 SQLite 内存库时需要 `check_same_thread=False`，生产 PostgreSQL 不需要该参数。
    """

    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入使用的 Session 生命周期。"""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
