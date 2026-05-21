FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Dépendances installées en premier pour profiter du cache Docker
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Code source et configuration Streamlit
COPY src/ ./src/
COPY .streamlit/ ./.streamlit/

ENV PYTHONUNBUFFERED=1
ENV TRANSFORMERS_VERBOSITY=error

EXPOSE 8501

# La base de données doit être montée via un volume :
#   docker run -v $(pwd)/data:/app/data ...
CMD ["uv", "run", "streamlit", "run", "src/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501"]
