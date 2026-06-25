"""健康检查路由。

该接口不访问数据库或模型服务，用于判断 FastAPI 进程是否存活；依赖检查会在后续
运维/监控接口中单独扩展。
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """返回轻量服务状态。"""

    return {"status": "ok"}
