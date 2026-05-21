from __future__ import annotations
import dataclasses
import uuid
import streamlit as st
from src.chain import build_graph, run_turn
from src.config import Settings, load_settings
from src.db import get_engine, get_user_by_email
from src.llm import get_llm


@st.cache_resource(show_spinner=False)
def _init_base():
    """Charge la configuration et le moteur de base de données — sans LLM."""
    settings = load_settings()
    engine = get_engine(settings.db_path)
    return settings, engine


@st.cache_resource(show_spinner="Chargement du modèle...")
def _get_graph(llm_backend: str):
    """Charge le LLM et compile le graphe — une entrée de cache par backend."""
    settings, engine = _init_base()
    settings = dataclasses.replace(settings, llm_backend=llm_backend)
    llm = get_llm(settings)
    return build_graph(
        llm, engine,
        classifier_strategy=settings.classifier_strategy,
        advisor_phone=settings.advisor_phone,
    )


def _sidebar_login(engine) -> dict | None:
    """Formulaire de connexion ou résumé du profil connecté."""
    with st.sidebar:
        _, col, _ = st.columns([0.15, 0.7, 0.15])
        with col:
            st.image("assets/Logo rond assistant virtuel client.png", use_container_width=True)
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
            with st.container(border=True):
                st.success("Vous êtes connecté(e)")
                st.caption(f"**Prénom :** {p['first_name']}")
                st.caption(f"**Nom :** {p['last_name']}")
                st.caption(f"**Email :** {p['email']}")
                st.caption(f"**Réf. client :** {p['user_id']}")
            if st.button("Se déconnecter", use_container_width=True):
                for key in ["profile", "messages", "thread_id", "last_state"]:
                    st.session_state.pop(key, None)
                st.rerun()

    return st.session_state.get("profile")

def _sidebar_options(settings: Settings) -> str:
    """Expander Options — retourne le backend LLM sélectionné ('local' | 'api').

    Si LLM_BACKEND=api  : toggle positionné sur API et désactivé.
    Si LLM_BACKEND=local : toggle positionné sur Local, modifiable.
    """
    forced_api = settings.llm_backend == "api"
    with st.sidebar:
        with st.expander("Options", expanded=False):
            use_api = st.toggle("API Mistral", value=forced_api, disabled=forced_api)
            if forced_api:
                st.caption("API Mistral hébergée (imposée par l'environnement)")
            else:
                st.caption("Local (modèle quantisé)" if not use_api else "API Mistral hébergée")
    return "api" if use_api else "local"


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
    st.markdown(
        """
        <style>
        [data-testid="stMarkdownContainer"] hr {
            margin-top: 0.25rem;
            margin-bottom: 1.25rem;
            border-top: 0.5px solid rgba(49, 51, 63, 0.2);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    settings, engine = _init_base()
    profile = _sidebar_login(engine)
    st.sidebar.divider()
    llm_backend = _sidebar_options(settings)

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
                graph = _get_graph(llm_backend)
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
