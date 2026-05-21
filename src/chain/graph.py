from __future__ import annotations
import json
import operator
import re
from functools import partial
from typing import Annotated, Any, TypedDict
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from sqlalchemy import Engine
from src.chain.input_check import ClassificationStrategy, build_classifier
from src.chain.prompts import ANSWER_FORMATTING_SYSTEM, SQL_GENERATION_SYSTEM
from src.db import run_select

# Mots-clés interdits dans le SQL généré
BLACKLIST_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|VACUUM)\b",
    re.IGNORECASE,
)

# Nombre de tours passés injectés dans le contexte SQL
_MAX_HISTORY = 5

class GrapheState(TypedDict, total=False):
    # Données présentes en entrée à la création
    user_id: int
    user_profile: dict[str, Any]
    question: str
    # Données renseignées par les nœuds du graphe lorsqu'il se déroule.
    intent: str | None
    intent_reason: str | None
    sql: str | None
    rows: list[dict[str, Any]] | None
    answer: str | None
    # Historique cumulatif des échanges géré par MemorySaver via operator.add
    history: Annotated[list[dict[str, str]], operator.add]

###############################################################################
##################            Noeuds du graphe               ##################
###############################################################################

# Noeud de classification d'intention. Analyse des données d'input.
def _node_classify_intent(state: GrapheState, *, classifier: Any) -> GrapheState:
    result = classifier.classify(state["question"])
    return {**state, "intent": result.intent, "intent_reason": result.reason}

# Noeud de classification d'intention. Analyse des données d'input.
def _route_after_classify(state: GrapheState) -> str:
    intent = state.get("intent")
    if intent in ("commande", "compte"):
        return "generate_sql"
    if intent == "action_commande":
        return "format_redirect"
    return "format_refusal"

# Noeud de renvoi vers un conseiller.
def _node_format_redirect(state: GrapheState, *, advisor_phone: str) -> GrapheState:
    answer = (
        "Je comprends votre demande et je souhaite vous aider au mieux. "
        f"Un conseiller humain va prendre le relais pour vous accompagner — "
        f"vous pouvez le contacter au {advisor_phone}."
    )
    return {**state, "answer": answer}

# Noeud de refus de réponse.
def _node_format_refusal(state: GrapheState) -> GrapheState:
    if state.get("intent") == "hostile":
        answer = "Je ne peux pas donner suite à cette demande."
    else:
        answer = (
            "Je suis uniquement disponible pour vous aider sur vos commandes "
            "et les informations de votre compte. N'hésitez pas à reformuler."
        )
    return {**state, "answer": answer}

# Noeud de génération de la requête SQL - 1er appel du LLM
def _node_generate_sql(state: GrapheState, *, llm: BaseChatModel) -> GrapheState:
    history = state.get("history") or []

    messages: list = [SystemMessage(content=SQL_GENERATION_SYSTEM)]

    # Injecte les 5 derniers échanges (question → SQL) pour assurer la mémoire court-terme
    # Les tours sans SQL valide (requête bloquée) sont ignorés : un AIMessage vide
    # provoquerait une erreur 400 côté API.
    for turn in history[-_MAX_HISTORY:]:
        sql_in_history = turn.get("sql", "")
        if not sql_in_history:
            continue
        messages.append(HumanMessage(content=turn["question"]))
        messages.append(AIMessage(content=sql_in_history))
    messages.append(HumanMessage(content=state["question"]))

    response = llm.invoke(messages)
    sql = str(response.content).strip()

    # Nettoyage avec retrait de backticks ou balises markdown.
    sql = re.sub(r"^```(?:sql)?|```$", "", sql, flags=re.IGNORECASE | re.MULTILINE).strip()

    return {**state, "sql": sql}

# Noeud d'exécution de la requête SQL
def _node_execute_sql(state: GrapheState, *, engine: Engine) -> GrapheState:
    sql = state.get("sql") or ""

    # Toutes les gardes ci-dessous retournent rows=None : le SQL n'a pas été exécuté,
    # ce qui déclenche la réponse courte "information non disponible" dans format_answer.
    if BLACKLIST_SQL.search(sql):
        return {**state, "rows": None, "sql": None}

    if not sql.lstrip().lower().startswith("select"):
        return {**state, "rows": None, "sql": None}

    if ":user_id" not in sql:
        return {**state, "rows": None, "sql": None}

    try:
        rows = run_select(engine, sql, {"user_id": state["user_id"]})
    except Exception:
        # None signale une erreur d'exécution (schéma manquant, colonne inexistante...)
        # à distinguer d'un résultat vide légitime (rows = []).
        rows = None
    return {**state, "rows": rows}

# Noeud de génération de la réponse - 2ème appel du LLM
def _node_format_answer(state: GrapheState, *, llm: BaseChatModel) -> GrapheState:
    profile = state["user_profile"]
    rows = state.get("rows")

    # rows = None → la requête SQL a échoué (table ou colonne absente du schéma).
    # Cas déterministe : on court-circuite le LLM pour éviter toute hallucination.
    if rows is None:
        answer = (
            "Je n'ai pas accès à cette information. "
            "Pour plus de détails, n'hésitez pas à contacter notre service client."
        )
        new_entry = [{"question": state["question"], "sql": state.get("sql") or "", "answer": answer}]
        return {**state, "answer": answer, "history": new_entry}

    # rows = [] → requête valide mais aucun résultat correspondant
    context = (
        f"Client : {profile.get('first_name')} {profile.get('last_name')} "
        f"({profile.get('email')}).\n"
        f"Question : {state['question']}\n"
        f"Résultats SQL ({len(rows)} ligne(s)) :\n"
        f"<données>\n"
        f"{json.dumps(rows, ensure_ascii=False, indent=2, default=str)}\n"
        f"</données>\n"
    )

    messages = [
        SystemMessage(content=ANSWER_FORMATTING_SYSTEM),
        HumanMessage(content=context),
    ]
    response = llm.invoke(messages)
    answer = str(response.content).strip()

    # Ajoute l'échange à l'historique
    # # operator.add concatène le dernier échange à la liste existante.
    new_entry = [{"question": state["question"], "sql": state.get("sql") or "", "answer": answer}]
    return {**state, "answer": answer, "history": new_entry}

# Construction du graphe
def build_graph(
    llm: BaseChatModel,
    engine: Engine,
    classifier_strategy: ClassificationStrategy = "llm",
    advisor_phone: str = "06.07.06.07.06",
) -> Any:
    classifier = build_classifier(classifier_strategy, llm=llm)

    graph = StateGraph(GrapheState)

    graph.add_node("classify_intent", partial(_node_classify_intent, classifier=classifier))
    graph.add_node("generate_sql", partial(_node_generate_sql, llm=llm))
    graph.add_node("execute_sql", partial(_node_execute_sql, engine=engine))
    graph.add_node("format_answer", partial(_node_format_answer, llm=llm))
    graph.add_node("format_redirect", partial(_node_format_redirect, advisor_phone=advisor_phone))
    graph.add_node("format_refusal", _node_format_refusal)

    graph.add_edge(START, "classify_intent")
    graph.add_conditional_edges("classify_intent", _route_after_classify)
    graph.add_edge("generate_sql", "execute_sql")
    graph.add_edge("execute_sql", "format_answer")
    graph.add_edge("format_answer", END)
    graph.add_edge("format_redirect", END)
    graph.add_edge("format_refusal", END)

    # MemorySaver persiste l'état (dont history) entre les tours d'un même thread_id.
    return graph.compile(checkpointer=MemorySaver())

# Run
def run_turn(
    compiled_graph: Any,
    *,
    user_id: int,
    user_profile: dict[str, Any],
    question: str,
    thread_id: str,
) -> GrapheState:
    initial: GrapheState = {
        "user_id": user_id,
        "user_profile": user_profile,
        "question": question,
        "intent": None,
        "intent_reason": None,
        "sql": None,
        "rows": None,
        "answer": None,
    }
    config = {"configurable": {"thread_id": thread_id}}
    return compiled_graph.invoke(initial, config=config)
