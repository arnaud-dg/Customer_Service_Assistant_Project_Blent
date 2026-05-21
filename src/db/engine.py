"""Connexion SQLAlchemy en lecture seule sur la base SQLite."""

from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Any
from sqlalchemy import Engine, create_engine, text


# Connexion à la base .db
@lru_cache(maxsize=1) # Mise en cache
def get_engine(db_path: Path) -> Engine:
    """Retourne un moteur SQLAlchemy en lecture seule pointant sur la base SQLite."""
    if not db_path.exists():
        raise FileNotFoundError(f"Base de données introuvable : {db_path}")

    # LEcture seule avec mode=ro ; uri=true : nécessaire pour passer une URI SQLite
    url = f"sqlite:///file:{db_path.as_posix()}?mode=ro&uri=true"
    return create_engine(url, future=True)

# Exécution d'une query
def run_select(engine: Engine, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Exécute un SELECT avec paramètres liés et retourne les lignes en dictionnaire"""
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        return [dict(row) for row in result.mappings()]

# Récupération du profil utilisateur par user_id
def get_user_profile(engine: Engine, user_id: int) -> dict[str, Any] | None:
    """Récupère le profil minimal d'un utilisateur (nom, prénom, email)."""
    sql = "SELECT user_id, first_name, last_name, email FROM users WHERE user_id = :uid"
    rows = run_select(engine, sql, {"uid": user_id})
    return rows[0] if rows else None


# Récupération du profil utilisateur par email
def get_user_by_email(engine: Engine, email: str) -> dict[str, Any] | None:
    """Récupère le profil d'un utilisateur à partir de son adresse email."""
    sql = "SELECT user_id, first_name, last_name, email FROM users WHERE email = :email"
    rows = run_select(engine, sql, {"email": email.strip()})
    return rows[0] if rows else None
