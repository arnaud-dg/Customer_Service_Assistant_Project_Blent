"""Configuration globale chargée depuis l'environnement."""

from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Charge .env à la racine du projet si présent
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    """Paramètres applicatifs (immuables)."""
    # Base de données
    db_path: Path
    # LLM
    llm_backend: str  # "api" | "local"
    mistral_api_key: str | None
    mistral_model: str
    local_model_id: str
    local_device_map: str
    # Classification d'intention
    classifier_strategy: str  # "llm" | "semantic"
    advisor_phone: str
    # Environnement
    env: str
    log_level: str

def _get_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variable d'environnement requise manquante : {name}")
    return value

def load_settings() -> Settings:
    """Construit les paramètres à partir des variables d'environnement."""
    backend = os.getenv("LLM_BACKEND", "api").lower()
    if backend not in {"api", "local"}:
        raise ValueError(f"LLM_BACKEND invalide : {backend!r} (attendu : 'api' ou 'local')")

    db_path = Path(os.getenv("DB_PATH", "data/raw/orders.db"))
    if not db_path.is_absolute():
        db_path = _PROJECT_ROOT / db_path

    classifier = os.getenv("CLASSIFIER_STRATEGY", "llm").lower()
    if classifier not in {"llm", "semantic"}:
        raise ValueError(f"CLASSIFIER_STRATEGY invalide : {classifier!r} (attendu : 'llm' ou 'semantic')")

    return Settings(
        db_path=db_path,
        llm_backend=backend,
        mistral_api_key=os.getenv("MISTRAL_API_KEY"),
        mistral_model=os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
        local_model_id=os.getenv("LOCAL_MODEL_ID", "mistralai/Mistral-7B-Instruct-v0.3"),
        local_device_map=os.getenv("LOCAL_DEVICE_MAP", "auto"),
        classifier_strategy=classifier,
        advisor_phone=os.getenv("ADVISOR_PHONE", "06.07.06.07.06"),
        env=os.getenv("ENV", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
