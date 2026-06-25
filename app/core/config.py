from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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
        return Field(default=self.openai_chat_model).default


@lru_cache
def get_settings() -> Settings:
    return Settings()

