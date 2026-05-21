from __future__ import annotations
import uuid
import streamlit as st
from src.chain import build_graph, run_turn
from src.config import load_settings
from src.db import get_engine, get_user_by_email
from src.llm import get_llm


@st.cache_resource(show_spinner="Initialisation...")
def _init_resources():
    """Charge la configuration, le LLM et compile le graphe une fois."""
    settings = load_settings()
    engine = get_engine(settings.db_path)
    llm = get_llm(settings)
    graph = build_graph(
        llm, engine,
        classifier_strategy=settings.classifier_strategy,
        advisor_phone=settings.advisor_phone,
    )
    return settings, engine, graph


def _sidebar_login(engine) -> dict | None:
    """Formulaire de connexion ou résumé du profil connecté."""
    with st.sidebar:
        st.subheader("Identification")

        if "profile" not in st.session_state:
            email = st.text_input("Adresse email", key="email_input")
            if st.button("Confirmer", use_container_width=True):
                if not email.strip():
                    st.error("Email non renseigné.")
                else:
                    profile = get_user_by_email(engine, email)
                    if profile is None:
                        st.error("Aucun compte associé à cet email.")
                    else:
                        st.session_state.profile = profile
                        st.session_state.thread_id = str(uuid.uuid4())
                        st.rerun()
        else:
            p = st.session_state.profile
            st.success("Vous êtes connecté(e)")
            with st.container(border=True):
                st.write(f"**Prénom :** {p['first_name']}")
                st.write(f"**Nom :** {p['last_name']}")
                st.write(f"**Email :** {p['email']}")
                st.write(f"**Réf. client :** {p['user_id']}")
            if st.button("Se déconnecter", use_container_width=True):
                for key in ["profile", "messages", "thread_id", "last_state"]:
                    st.session_state.pop(key, None)
                st.rerun()

    return st.session_state.get("profile")


def _sidebar_log(state: dict) -> None:
    """Affiche les détails techniques du dernier échange dans la sidebar."""
    with st.sidebar:
        st.divider()
        with st.expander("Log"):
            intent = state.get("intent") or ""
            reason = state.get("intent_reason") or ""
            st.caption(f"Intent : `{intent}`")
            if reason:
                st.caption(reason)
            st.code(state.get("sql") or "(aucune requête exécutée)", language="sql")
            st.json(state.get("rows") or [])


def _welcome_message(first_name: str) -> str:
    return (
        f"Bonjour {first_name} ! Je suis votre conseiller virtuel. "
        "Je peux vous renseigner sur vos commandes et les informations de votre compte. "
        "Comment puis-je vous aider ?"
    )


def main() -> None:
    st.set_page_config(page_title="Assistant service client", page_icon="🛒")
    st.title("Assistant service client")

    settings, engine, graph = _init_resources()
    profile = _sidebar_login(engine)

    if profile is None:
        st.info("Identifiez-vous dans la barre latérale pour commencer.")
        return

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": _welcome_message(profile["first_name"])}
        ]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Posez votre question ...")

    if question:
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
                    thread_id=st.session_state.thread_id,
                )
            answer = state.get("answer") or "Désolé, je n'ai pas pu traiter votre demande."
            st.markdown(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})

        if settings.env == "development":
            st.session_state.last_state = state

    if settings.env == "development" and "last_state" in st.session_state:
        _sidebar_log(st.session_state.last_state)


if __name__ == "__main__":
    main()
