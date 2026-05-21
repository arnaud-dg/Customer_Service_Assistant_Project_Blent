"""Backends LLM (API Mistral hébergée ou modèle local quantisé selon le choix utilisateur)."""
from src.llm.factory import get_llm
__all__ = ["get_llm"]
