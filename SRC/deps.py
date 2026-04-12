import redis.asyncio as redis
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from config import get_settings

_settings = get_settings()


async def get_redis():
    client = redis.from_url(_settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


def get_chroma_client():
    import chromadb

    return chromadb.HttpClient(host=_settings.chroma_host, port=_settings.chroma_port)
