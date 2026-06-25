"""项目级异常类型。

service/domain 层抛出这些异常，API 层统一转换为 HTTP 响应；这样业务逻辑不需要导入
FastAPI Response，也不会散落状态码判断。
"""

from fastapi import status


class AppError(Exception):
    """所有可预期业务异常的基类。"""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "APP_ERROR"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class BadRequestError(AppError):
    """请求参数或可解析业务值无效。"""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "BAD_REQUEST"


class NotFoundError(AppError):
    """请求的业务资源不存在。"""

    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class ConflictError(AppError):
    """创建型接口遇到资源冲突。"""

    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"


class ServiceUnavailableError(AppError):
    """数据库、模型服务等外部依赖暂时不可用。"""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "SERVICE_UNAVAILABLE"
