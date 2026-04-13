import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from config import get_settings
from database import engine
from deps import get_chroma_client, get_redis

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness():
    return {"status": "ok"}


@router.get("/ready")
async def readiness(redis_client: Redis = Depends(get_redis)):
    checks: dict[str, str] = {}
    settings = get_settings()

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = str(e)
    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = str(e)
    try:
        client = get_chroma_client()
        client.heartbeat()
        checks["chromadb"] = "ok"
    except Exception as e:
        checks["chromadb"] = str(e)

    try:
        need_gen = settings.generation_backend.upper() == "OLLAMA"
        need_emb = settings.embedding_backend.upper() == "OLLAMA"
        need_cls = settings.generation_backend.upper() == "OLLAMA"
        needed: set[str] = set()
        if need_gen:
            needed.add(settings.generation_model_id)
        if need_emb:
            needed.add(settings.embedding_model_id)
        if need_cls:
            needed.add(settings.classifier_model_id)
        if not needed:
            checks["ollama"] = "skipped (no Ollama-backed models in use)"
        else:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{settings.ollama_base_url}/api/tags")
                r.raise_for_status()
                models = [m["name"] for m in r.json().get("models", [])]
                missing = needed - set(models)
                if missing:
                    checks["ollama"] = f"reachable but missing models: {', '.join(sorted(missing))}"
                else:
                    checks["ollama"] = "ok"
    except Exception as e:
        checks["ollama"] = f"unreachable: {e}"

    all_ok = all(
        v == "ok" or (k == "ollama" and str(v).startswith("skipped"))
        for k, v in checks.items()
    )
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "degraded", "checks": checks},
    )
