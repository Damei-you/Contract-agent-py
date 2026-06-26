"""应用配置。

Python 版直接用 pydantic-settings 从环境变量读取配置；字段默认值就是本地开发默认值。
部署或联调时只需要设置同名环境变量覆盖即可。
"""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """运行时配置项。

    OpenAI-compatible 参数由 LangChain 工厂消费；RAG 参数由检索和向量写入组件使用。
    """

    app_env: str = "local"
    app_port: int = 8088
    database_url: str = "postgresql+psycopg://postgres:123456@localhost:5432/contract-agent-py"

    openai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode"
    openai_api_key: str = ""
    compatible_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("API_KEY", "api-key"),
        exclude=True,
    )
    openai_chat_model: str = "qwen-plus"
    openai_embedding_model: str = "text-embedding-v3"
    openai_embedding_dimensions: int = 1024
    embedding_batch_size: int = 10
    vector_collection_name: str = "contract_agent"
    rag_contract_top_k: int = 5
    rag_policy_top_k: int = 5

    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "contract-agent-python"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def model_post_init(self, __context: object) -> None:
        """兼容参考项目的 API Key 兜底规则。

        `contract-agent-mvp` 支持 `${OPENAI_API_KEY:${API_KEY:${api-key:}}}`；
        Python 版保留同样语义，避免本地只配置 `API_KEY` 时向量入库被误判为未配置。
        """

        if not self.openai_api_key and self.compatible_api_key:
            self.openai_api_key = self.compatible_api_key

    @property
    def langchain_model_name(self) -> str:
        """保留一个语义化别名，避免调用方关心具体配置字段名。"""

        return self.openai_chat_model


@lru_cache
def get_settings() -> Settings:
    """缓存配置对象，避免每次依赖注入都重新读取环境。"""

    return Settings()
