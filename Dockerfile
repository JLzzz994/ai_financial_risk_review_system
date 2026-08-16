FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir uv && uv sync --no-dev
COPY app ./app
COPY engines ./engines
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY var ./var
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
