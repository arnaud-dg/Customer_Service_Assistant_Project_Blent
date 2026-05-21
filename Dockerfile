FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN git clone https://github.com/arnaud-dg/Customer_Service_Assistant_Project_Blent.git /app
WORKDIR /app

# Dépendances de développement
RUN uv sync --extra dev

# Pour le backend local (modèle quantisé, ~15 Go) :
# RUN uv sync --extra dev --extra local

ENV PYTHONUNBUFFERED=1
ENV TRANSFORMERS_VERBOSITY=error
# Evite le warning hardlink uv dans les environnements conteneurisés
ENV UV_LINK_MODE=copy

EXPOSE 8501

# Renseigner MISTRAL_API_KEY au lancement :
#   docker run -e MISTRAL_API_KEY=xxx ...
#   ou docker run --env-file .env ...
CMD ["uv", "run", "streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
