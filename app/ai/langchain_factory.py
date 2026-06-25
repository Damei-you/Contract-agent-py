import os
from typing import Any

from app.core.config import Settings


def configure_langsmith(settings: Settings) -> None:
    if settings.langsmith_tracing:
        os.environ["LANGSMITH_TRACING"] = "true"
        if settings.langsmith_api_key:
            os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project


def create_chat_model(settings: Settings) -> Any:
    configure_langsmith(settings)
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.openai_chat_model,
        api_key=settings.openai_api_key or None,
        base_url=settings.openai_base_url,
        temperature=0.2,
    )


def create_embeddings(settings: Settings) -> Any:
    configure_langsmith(settings)
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key or None,
        base_url=settings.openai_base_url,
    )

