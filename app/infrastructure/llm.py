"""LangChain chat model client, initialized from application `Settings`."""

import logging
from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.infrastructure.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_chat_model() -> BaseChatModel:
    """Return a cached chat model client.

    Typed as the provider-neutral `BaseChatModel` rather than `ChatOpenAI`
    so callers (e.g. `DialogService`) don't depend on the concrete
    provider — switching to Gemini/Qwen later shouldn't require changing
    calling code (see `.ai-factory/DESCRIPTION.md`).
    """
    settings = get_settings()
    logger.debug("chat model client created", extra={"model": settings.openai_chat_model})
    return ChatOpenAI(model=settings.openai_chat_model, api_key=settings.openai_api_key)
