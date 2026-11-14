# Project workflow

- Use `uv sync` for dependencies and `uv run uvicorn app.main:app --reload` for the local playground.
- Run `uv run pytest -q` for receiver, signing, delivery/retry, dashboard, and learning-lab tests.
- Run `uv run mkdocs build --strict` to verify documentation. Serve docs on a separate port with `uv run mkdocs serve -a 127.0.0.1:8001`.
- The dashboard is standalone HTML/CSS/JavaScript in `app/static/dashboard.html`, served by FastAPI; no frontend build is required.
- Learning experiments at `POST /lab/{scenario}` invoke the actual receiver using an in-process HTTPX ASGI transport and never expose the configured secret.
- State is in memory. Duplicate receipts are recorded and flagged; flaky/dead endpoints simulate response statuses only and do not record receiver events.
