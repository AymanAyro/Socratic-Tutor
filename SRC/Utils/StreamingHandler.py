from collections.abc import AsyncIterator
from typing import Any


async def collect_stream(stream: AsyncIterator[str]) -> tuple[str, list[str]]:
    chunks: list[str] = []
    async for c in stream:
        chunks.append(c)
    return "".join(chunks), chunks


def sse_event(event: str, data: str) -> str:
    lines = [f"event: {event}", f"data: {data.replace(chr(10), ' ').replace(chr(13), '')}"]
    return "\n".join(lines) + "\n\n"
