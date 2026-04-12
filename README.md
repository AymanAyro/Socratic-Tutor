# Socratic Tutor

Production-style monorepo: FastAPI backend (`SRC/`), React + Vite frontend (`frontend/`), Docker Compose for Postgres, Redis, ChromaDB, Prometheus, and Grafana.

## Quick start (local split-stack)

This is the usual path: **infra in Docker**, **API + Vite on the host**.

1. **Bootstrap infra:** from the repo root run `.\dev.ps1` (Windows) or `./dev.sh` (Unix). This creates missing env files from examples (`SRC/.env`, `Docker/env/.env.postgres`, `.env.grafana`, `.env.app`) and runs `docker compose -f Docker/docker-compose.dev.yml up -d` (Postgres, Redis, Chroma on host port **8001**, Prometheus, Grafana).

   **Postgres host port is `15432`** (mapped to container `5432`) so a local PostgreSQL on `5432` and Windows Hyper-V reserved ranges (e.g. `5433+`) do not block you. `SRC/.env.example` and defaults use `POSTGRES_PORT=15432`.

2. **Wait for DB/cache:** Postgres and Redis have Docker healthchecks; give Chroma a few seconds on first start.

3. **Backend:** `cd SRC && uv sync --extra dev && uv run alembic upgrade head && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000`  
   Use `uv sync --extra dev` so `pytest` is available. For **verbose terminal logs**, set `LOG_LEVEL=DEBUG` in `SRC/.env` (and optionally `SQLALCHEMY_ECHO=true` for SQL), or run Uvicorn with `--log-level debug`. Each request logs `->` / `<-` with status and timing; ingest logs KG + vector steps; unhandled errors print a full traceback.

4. **Verify data plane** (Postgres, Redis, Chroma reachable from the API):  
   `.\scripts\verify-stack.ps1` (Windows) or `./scripts/verify-stack.sh` (Unix), default base URL `http://127.0.0.1:8000`. Expect `OK: postgres, redis, chromadb`.

5. **LLM:** start [Ollama](https://ollama.com) locally, then pull the models that match `SRC/.env` (defaults match `.env.example`):

   ```bash
   ollama pull phi3:mini
   ollama pull qwen2.5:7b
   ollama pull nomic-embed-text
   ```

   Or set `GENERATION_BACKEND=GEMINI` and `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) in `SRC/.env`. Gemini uses **LangChain** [`langchain-google-genai`](https://github.com/langchain-ai/langchain-google) on top of Google’s [`google-genai`](https://github.com/googleapis/python-genai) client; see `SRC/.env.example` for optional Vertex settings.

6. **UI:** `cd frontend && npm install && npm run dev` — open **http://127.0.0.1:24678** (default dev port; Vite proxies `/api` to port 8000). This avoids Windows `EACCES` on **5173** from Hyper-V reserved ranges. To use **5173** instead: `$env:VITE_DEV_SERVER_PORT=5173; npm run dev` (PowerShell) or `VITE_DEV_SERVER_PORT=5173 npm run dev` (Unix).

## Full stack (Docker)

```bash
cd Docker
docker compose up --build
```

- UI + API through Nginx: http://localhost:8888  
- **Readiness:** `curl http://localhost:8888/api/v1/health/ready` — all checks should be `ok` when Postgres, Redis, and Chroma are up.  
- The FastAPI image runs **`alembic upgrade head` on container start** (entrypoint); you do not need a separate migration command for first boot.  
- Ensure `Docker/env/.env.app` has `OLLAMA_BASE_URL` pointing at a reachable Ollama instance (e.g. `http://host.docker.internal:11434` on Docker Desktop). `dev.ps1` / `dev.sh` create `.env.app` from the example if it is missing.

Optional: after the API is up, `./scripts/verify-stack.sh http://localhost:8000` hits the container directly; through Nginx use `./scripts/verify-stack.sh http://localhost:8888`.

## Tests & eval

- Backend: `cd SRC && uv sync --extra dev && uv run pytest`
- Classifier eval: `cd SRC && uv run python -m eval_harness.run_eval` (requires a working LLM)

## Frameworks

- **LlamaIndex** — document chunking (`SentenceSplitter`), Chroma vector index (`ChromaVectorStore` over HTTP), metadata-filtered retrieval (`MetadataFilters` on `concept_id`).
- **LangChain** — `ChatOllama` / `ChatGoogleGenerativeAI`, embeddings, and `with_structured_output` for the understanding classifier; optional **LangSmith** via `LANGCHAIN_TRACING_V2` and `LANGCHAIN_API_KEY` in `.env`.

## Scaling (infra)

Heavy ingest and large corpora benefit from background workers (queue + worker processes) and a managed vector database; that is independent of the LlamaIndex/LangChain integration.

## Specification

See [socratic_tutor_project.md](socratic_tutor_project.md) for architecture, prompts, and API details.
