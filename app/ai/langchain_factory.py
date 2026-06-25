"""LangChain 组件工厂。

模型、embedding 和 LangSmith tracing 集中在这里创建，后续 chain/graph 不直接读取环境变量，
便于测试时替换为 fake model 或 fake embedding。
"""

import os
from typing import Any

from app.core.config import Settings


def configure_langsmith(settings: Settings) -> None:
    """按配置开启 LangSmith tracing。

    tracing 是可选调试能力；本地没有 API Key 时不应影响业务 API 启动。
    """

    if settings.langsmith_tracing:
        os.environ["LANGSMITH_TRACING"] = "true"
        if settings.langsmith_api_key:
            os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project


def create_chat_model(settings: Settings) -> Any:
    """创建 OpenAI-compatible ChatModel。

    DashScope/OpenAI 等兼容服务都通过 base_url + api_key 进入 LangChain。
    """

    configure_langsmith(settings)
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.openai_chat_model,
        api_key=settings.openai_api_key or None,
        base_url=settings.openai_base_url,
        temperature=0.2,
    )


def create_embeddings(settings: Settings) -> Any:
    """创建 OpenAI-compatible Embeddings。

    embedding 维度必须和后续 pgvector 表结构一致，具体校验会在向量阶段补充。
    """

    configure_langsmith(settings)
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key or None,
        base_url=settings.openai_base_url,
    )
