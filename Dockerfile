FROM python:3.12-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --locked --no-dev --no-cache

COPY . .

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

CMD ["sh", "-c", "uv run --no-sync uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
