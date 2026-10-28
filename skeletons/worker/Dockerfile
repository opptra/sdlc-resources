FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project
COPY backend ./backend
ENV PATH="/app/.venv/bin:$PATH"
# Job commands are `python -m app...`. The package is in backend/.
ENV PYTHONPATH="/app/backend"
CMD ["python", "-m", "app.main"]
