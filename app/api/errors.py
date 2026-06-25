"""统一 HTTP 异常映射。

业务层通过 AppError 子类表达稳定错误语义，API 层在这里转换为前端可依赖的
`code + detail` 响应，避免每个路由重复 try/except。
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError


def register_exception_handlers(app: FastAPI) -> None:
    """注册项目级异常处理器。

    RequestValidationError 被统一降级为 400，是为了对齐参考项目的“入参错误”
    语义，而不是暴露 FastAPI 默认的 422。
    """

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.errors(), "code": "BAD_REQUEST"},
        )
