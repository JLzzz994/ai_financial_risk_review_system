FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

ARG INSTALL_RAG_DEPS=false

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY engines ./engines
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY seed_demo_data.py ./seed_demo_data.py
COPY var ./var
RUN if [ "$INSTALL_RAG_DEPS" = "true" ]; then \
      uv sync --frozen --no-dev --extra rag; \
    else \
      uv sync --frozen --no-dev; \
    fi

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
