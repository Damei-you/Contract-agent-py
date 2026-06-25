from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.routes import contracts, health, policies


def create_app() -> FastAPI:
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
        return {"service": "contract-agent-python", "status": "ok"}

    return app


app = create_app()

