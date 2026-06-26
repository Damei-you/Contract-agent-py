"""PyCharm/FastAPI 兼容入口。

业务应用实际组装逻辑放在 `app.main`；根目录入口只负责让 IDE 和 `uvicorn main:app`
都能明确找到 FastAPI 应用对象。
"""

from fastapi import FastAPI

from app.core.config import get_settings
from app.main import create_app

app: FastAPI = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("main:app", host="127.0.0.1", port=settings.app_port, reload=True)
