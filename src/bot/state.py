"""État partagé du graphe LangGraph."""

from __future__ import annotations

from typing import Any, TypedDict


class BotState(TypedDict, total=False):
    """État manipulé par les nœuds du graphe.

    Champs marqués `total=False` car certains ne sont remplis qu'après
    exécution du nœud correspondant.
    """

    # Toujours présents en entrée
    user_id: int
    user_profile: dict[str, Any]
    question: str

    # Remplis par les nœuds suivants
    intent: str | None
    sql: str | None
    rows: list[dict[str, Any]] | None
    answer: str | None
