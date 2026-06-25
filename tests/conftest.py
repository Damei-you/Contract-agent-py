"""测试夹具。

阶段 0-2 的测试只验证业务表和 API 语义，因此使用 SQLite 内存库即可快速反馈；
pgvector/PostgreSQL 集成测试会在向量阶段再补充。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def db_session() -> Session:
    """为每个测试创建隔离的内存数据库。"""

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    """覆盖 FastAPI 数据库依赖，让 API 测试使用同一个测试事务上下文。"""

    def override_get_db():
        """将应用的 get_db 绑定到当前测试 Session。"""

        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
