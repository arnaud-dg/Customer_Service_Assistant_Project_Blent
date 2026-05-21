"""Sélection du backend LLM selon la configuration décrite dans src/config.py"""
from __future__ import annotations
from langchain_core.language_models import BaseChatModel
from src.config import Settings

def get_llm(settings: Settings) -> BaseChatModel:
    """Retourne une instance de chat model LangChain selon `LLM_BACKEND`."""

    # Test du type de modèle souhaité : API vs Local
    if settings.llm_backend == "api":
        if not settings.mistral_api_key:
            raise RuntimeError("MISTRAL_API_KEY est requis quand LLM_BACKEND=api")
        
        from langchain_mistralai import ChatMistralAI

        return ChatMistralAI(
            model=settings.mistral_model,
            api_key=settings.mistral_api_key,
            temperature=0,
        )

    if settings.llm_backend == "local":
        from src.llm.mistral_local import get_local_llm

        return get_local_llm(
            model_id=settings.local_model_id,
            device_map=settings.local_device_map,
        )

    raise ValueError(f"Backend LLM inconnu : {settings.llm_backend!r}")
