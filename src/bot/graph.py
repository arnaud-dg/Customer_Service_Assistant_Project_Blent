"""Graphe LangGraph minimal : generate_sql → execute_sql → format_answer.

Volontairement réduit pour servir de point de départ. Les nœuds prévus
(routage sémantique, classification d'intention, garde-fous avancés, escalade
humaine) seront ajoutés lors des étapes 2 et 3 du projet.
"""

from __future__ import annotations

import json
import re
from functools import partial
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from sqlalchemy import Engine

from src.bot.prompts import ANSWER_FORMATTING_SYSTEM, SQL_GENERATION_SYSTEM
from src.bot.state import BotState
from src.db import run_select

# Mots-clés interdits dans le SQL généré (garde-fou minimal, à compléter en étape 3).
_FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM)\b",
    re.IGNORECASE,
)


def _node_generate_sql(state: BotState, *, llm: BaseChatModel) -> BotState:
    """Demande au LLM de produire la requête SQL pour la question courante."""
    messages = [
        SystemMessage(content=SQL_GENERATION_SYSTEM),
        HumanMessage(content=state["question"]),
    ]
    response = llm.invoke(messages)
    sql = str(response.content).strip()

    # Nettoyage défensif : retire d'éventuels backticks ou balises markdown.
    sql = re.sub(r"^```(?:sql)?|```$", "", sql, flags=re.IGNORECASE | re.MULTILINE).strip()

    return {**state, "sql": sql}


def _node_execute_sql(state: BotState, *, engine: Engine) -> BotState:
    """Valide la requête (garde-fou minimal) et l'exécute avec `user_id` lié."""
    sql = state.get("sql") or ""

    if _FORBIDDEN_SQL.search(sql):
        return {**state, "rows": [], "sql": None}

    if not sql.lstrip().lower().startswith("select"):
        return {**state, "rows": [], "sql": None}

    # Le prompt impose `:user_id` ; on lie explicitement la valeur de session.
    rows = run_select(engine, sql, {"user_id": state["user_id"]})
    return {**state, "rows": rows}


def _node_format_answer(state: BotState, *, llm: BaseChatModel) -> BotState:
    """Reformule les lignes en une réponse naturelle adressée au client."""
    profile = state["user_profile"]
    rows = state.get("rows") or []

    context = (
        f"Client : {profile.get('first_name')} {profile.get('last_name')} "
        f"({profile.get('email')}).\n"
        f"Question : {state['question']}\n"
        f"Résultats SQL ({len(rows)} ligne(s)) :\n"
        f"{json.dumps(rows, ensure_ascii=False, indent=2, default=str)}\n"
    )

    messages = [
        SystemMessage(content=ANSWER_FORMATTING_SYSTEM),
        HumanMessage(content=context),
    ]
    response = llm.invoke(messages)
    return {**state, "answer": str(response.content).strip()}


def build_graph(llm: BaseChatModel, engine: Engine) -> Any:
    """Construit et compile le graphe LangGraph."""
    graph = StateGraph(BotState)

    graph.add_node("generate_sql", partial(_node_generate_sql, llm=llm))
    graph.add_node("execute_sql", partial(_node_execute_sql, engine=engine))
    graph.add_node("format_answer", partial(_node_format_answer, llm=llm))

    graph.add_edge(START, "generate_sql")
    graph.add_edge("generate_sql", "execute_sql")
    graph.add_edge("execute_sql", "format_answer")
    graph.add_edge("format_answer", END)

    return graph.compile()


def run_turn(
    compiled_graph: Any,
    *,
    user_id: int,
    user_profile: dict[str, Any],
    question: str,
) -> BotState:
    """Exécute un tour de conversation et retourne l'état final."""
    initial: BotState = {
        "user_id": user_id,
        "user_profile": user_profile,
        "question": question,
        "intent": None,
        "sql": None,
        "rows": None,
        "answer": None,
    }
    return compiled_graph.invoke(initial)
