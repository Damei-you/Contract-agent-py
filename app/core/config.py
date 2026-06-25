"""应用配置。

配置来源优先环境变量，其次 `.env` 文件；这样本地开发、测试和容器部署可以共用同一套
Settings 对象。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """运行时配置项。

    OpenAI-compatible 参数由 LangChain 工厂消费；RAG 参数在后续检索阶段使用。
    """

    app_env: str = "local"
    app_port: int = 8000
    database_url: str = "postgresql+psycopg://postgres:123456@localhost:5432/contract_agent"

    openai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode"
    openai_api_key: str = ""
    openai_chat_model: str = "qwen-plus"
    openai_embedding_model: str = "text-embedding-v3"
    openai_embedding_dimensions: int = 1024
    embedding_batch_size: int = 10
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

    @property
    def langchain_model_name(self) -> str:
        """保留一个语义化别名，避免调用方关心具体配置字段名。"""

        return self.openai_chat_model


@lru_cache
def get_settings() -> Settings:
    """缓存配置对象，避免每次依赖注入都重新读取 `.env`。"""

    return Settings()
