"""Interface Streamlit minimale pour discuter avec le bot."""

from __future__ import annotations

import streamlit as st

from src.bot import build_graph, run_turn
from src.config import load_settings
from src.db import get_engine, get_user_profile
from src.llm import get_llm


@st.cache_resource(show_spinner="Initialisation du bot...")
def _init_pipeline():
    """Charge la configuration, le LLM, le moteur SQL et compile le graphe une fois."""
    settings = load_settings()
    engine = get_engine(settings.db_path)
    profile = get_user_profile(engine, settings.session_user_id)
    if profile is None:
        raise RuntimeError(
            f"Utilisateur de session introuvable (user_id={settings.session_user_id})."
        )
    llm = get_llm(settings)
    graph = build_graph(llm, engine)
    return settings, profile, graph


def main() -> None:
    st.set_page_config(page_title="Assistant service client", page_icon="🛒")
    st.title("Assistant service client")

    settings, profile, graph = _init_pipeline()

    with st.sidebar:
        st.subheader("Session")
        st.write(f"**Client :** {profile['first_name']} {profile['last_name']}")
        st.write(f"**Email :** {profile['email']}")
        st.write(f"**user_id :** {profile['user_id']}")
        st.caption(f"Backend LLM : `{settings.llm_backend}`")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Posez votre question sur vos commandes...")
    if not question:
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Recherche en cours..."):
            state = run_turn(
                graph,
                user_id=profile["user_id"],
                user_profile=profile,
                question=question,
            )
        answer = state.get("answer") or "Désolé, je n'ai pas pu traiter votre demande."
        st.markdown(answer)

        if settings.env == "development":
            with st.expander("Détails techniques"):
                st.code(state.get("sql") or "(aucune requête exécutée)", language="sql")
                st.json(state.get("rows") or [])

    st.session_state.messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
