"""API schema 基类。

项目内部使用 snake_case，HTTP JSON 与参考前端保持 camelCase；统一在这里处理别名，
避免每个 DTO 重复声明字段 alias。
"""

from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    """将 snake_case 字段名转换为 camelCase 响应字段。"""

    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class ApiModel(BaseModel):
    """所有 API DTO 的共同配置。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
