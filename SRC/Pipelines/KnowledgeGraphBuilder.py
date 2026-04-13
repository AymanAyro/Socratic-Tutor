import json
import logging
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from Models.Content import Concept, ConceptEdge
from Stores.LLM.factory import get_generation_client
from config import get_settings

logger = logging.getLogger(__name__)


KG_PROMPT = """You extract a small concept graph from educational text.
Return JSON only:
{
  "concepts": [{"name": string, "description": string, "difficulty_level": number, "parentConcept": string|null, "pageRef": string|null}],
  "edges": [{"from_name": string, "to_name": string, "relationship": string}]
}
Extract as many distinct technical concepts as useful (target 12-40 when available).
Prefer a hierarchy via parentConcept when possible. Include approximate pageRef when present.
Relationships like "prerequisite_of", "example_of", "part_of".
"""


def _parse_kg_json(raw: str) -> dict:
    t = raw.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError as e:
        m = re.search(r"\{[\s\S]*\}", t)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        logger.error("KG JSON parse failed: %s. Raw (first 800 chars): %r", e, t[:800])
        raise ValueError(
            "The generation model did not return valid JSON for the concept graph. "
            "Check Ollama is running, the model supports JSON mode, and try again."
        ) from e


class KnowledgeGraphBuilder:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._client = get_generation_client()
        self._settings = get_settings()

    async def build_from_text(self, document_id: uuid.UUID, text_sample: str) -> tuple[list[Concept], list[ConceptEdge]]:
        sample = text_sample[:12000]
        user = (
            "Source text:\n"
            f"{sample}\n\n"
            "Extract the concept graph now and return JSON only."
        )
        logger.info(
            "KG: calling generation model=%s (chars=%s)",
            self._settings.generation_model_id,
            len(sample),
        )
        try:
            raw, _ = await self._client.generate(
                user,
                system=KG_PROMPT,
                model=self._settings.generation_model_id,
                json_mode=True,
            )
        except Exception as e:
            logger.exception("KG: LLM generation failed")
            raise ValueError(
                "Concept graph generation failed. Is Ollama (or Gemini) running and is "
                f"GENERATION_MODEL_ID pulled / valid? Details: {e}"
            ) from e
        data = _parse_kg_json(raw)
        concepts: list[Concept] = []
        name_to_id: dict[str, uuid.UUID] = {}
        for c in data.get("concepts") or []:
            cid = uuid.uuid4()
            name = str(c.get("name") or "Concept").strip()[:512]
            name_to_id[name] = cid
            concepts.append(
                Concept(
                    id=cid,
                    document_id=document_id,
                    name=name,
                    description=(
                        (
                            (c.get("description") or "")
                            + (
                                f" Parent: {c.get('parentConcept')}."
                                if c.get("parentConcept")
                                else ""
                            )
                            + (f" Ref: {c.get('pageRef')}." if c.get("pageRef") else "")
                        )[:8000]
                    )
                    or None,
                    difficulty_level=int(c.get("difficulty_level") or 1),
                )
            )
        if not concepts:
            cid = uuid.uuid4()
            concepts.append(
                Concept(
                    id=cid,
                    document_id=document_id,
                    name="Main ideas",
                    description="Auto-generated root concept",
                    difficulty_level=1,
                )
            )
            name_to_id["Main ideas"] = cid

        self._db.add_all(concepts)
        await self._db.flush()

        edges: list[ConceptEdge] = []
        for e in data.get("edges") or []:
            fn = str(e.get("from_name") or "").strip()
            tn = str(e.get("to_name") or "").strip()
            fid = name_to_id.get(fn)
            tid = name_to_id.get(tn)
            if fid and tid and fid != tid:
                edges.append(
                    ConceptEdge(
                        id=uuid.uuid4(),
                        from_concept_id=fid,
                        to_concept_id=tid,
                        relationship=str(e.get("relationship") or "related")[:128],
                    )
                )
        if edges:
            self._db.add_all(edges)
        logger.info(
            "KG: document=%s concepts=%s edges=%s",
            document_id,
            len(concepts),
            len(edges),
        )
        return concepts, edges
