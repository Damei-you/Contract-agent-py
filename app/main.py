"""FastAPI 应用入口。

这里只负责组装路由和全局异常处理，业务用例放在 service 层，避免 HTTP 框架细节渗透到领域逻辑。
"""

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.routes import contracts, health, policies


def create_app() -> FastAPI:
    """创建应用实例，供 uvicorn、测试和未来 ASGI 部署复用。"""

    app = FastAPI(
        title="Contract Agent Python",
        version="0.1.0",
        description="Python rebuild of the financial contract approval agent MVP.",
    )
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(contracts.router)
    app.include_router(policies.router)

    @app.get("/", tags=["health"])
    def root() -> dict[str, str]:
        """根路径仅作为轻量探活，不承载业务语义。"""

        return {"service": "contract-agent-python", "status": "ok"}

    return app


app = create_app()
