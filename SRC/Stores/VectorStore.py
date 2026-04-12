from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable

import chromadb
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.vector_stores.types import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)
from llama_index.embeddings.langchain import LangchainEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from Stores.LLM.langchain_factory import get_langchain_embeddings
from config import get_settings

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 50


class VectorStore:
    """Chroma via LlamaIndex (HTTP client); collection names `doc_{document_id}`."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._raw_client = chromadb.HttpClient(
            host=self._settings.chroma_host,
            port=self._settings.chroma_port,
        )

    def _collection_name(self, document_id: uuid.UUID) -> str:
        return f"doc_{document_id}"

    def _chroma_vector_store(self, document_id: uuid.UUID) -> ChromaVectorStore:
        return ChromaVectorStore.from_params(
            collection_name=self._collection_name(document_id),
            host=self._settings.chroma_host,
            port=self._settings.chroma_port,
        )

    def _embed_model(self) -> LangchainEmbedding:
        return LangchainEmbedding(langchain_embeddings=get_langchain_embeddings())

    def build_index_from_text(
        self,
        document_id: uuid.UUID,
        full_text: str,
        concept_id: uuid.UUID,
        title_fallback: str,
        progress_callback: "Callable[[int, int, int], None] | None" = None,
    ) -> int:
        """Replace collection contents with LlamaIndex chunks + embeddings.

        ``progress_callback(batch_num, total_batches, embedded_so_far)`` is
        called after each batch completes so callers can stream progress.
        """
        logger.info(
            "VectorStore: build_index doc=%s chroma=%s:%s",
            document_id,
            self._settings.chroma_host,
            self._settings.chroma_port,
        )
        self.delete_document_collection(document_id)
        text = full_text.strip() or title_fallback
        doc = Document(
            text=text,
            metadata={"concept_id": str(concept_id), "document_id": str(document_id)},
        )
        splitter = SentenceSplitter(chunk_size=900, chunk_overlap=120)
        nodes = splitter.get_nodes_from_documents([doc])
        if not nodes:
            doc = Document(text=title_fallback, metadata={"concept_id": str(concept_id)})
            nodes = splitter.get_nodes_from_documents([doc])

        total = len(nodes)
        vs = self._chroma_vector_store(document_id)
        embed_model = self._embed_model()
        t0 = time.perf_counter()
        total_batches = (total + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE

        logger.info(
            "VectorStore: embedding %s nodes in %s batches into doc_%s",
            total, total_batches, document_id,
        )

        for i in range(0, total, EMBED_BATCH_SIZE):
            batch = nodes[i : i + EMBED_BATCH_SIZE]
            batch_num = i // EMBED_BATCH_SIZE + 1
            logger.info(
                "VectorStore: batch %s/%s (%s-%s of %s nodes)...",
                batch_num, total_batches, i + 1, min(i + len(batch), total), total,
            )
            storage_ctx = StorageContext.from_defaults(vector_store=vs)
            VectorStoreIndex(
                batch,
                storage_context=storage_ctx,
                embed_model=embed_model,
                show_progress=False,
            )
            if progress_callback:
                progress_callback(batch_num, total_batches, min(i + len(batch), total))

        elapsed = time.perf_counter() - t0
        logger.info(
            "VectorStore: index build complete — %s nodes in %.1fs (%.1f nodes/s)",
            total, elapsed, total / elapsed if elapsed > 0 else 0,
        )
        return total

    def query_by_concept(
        self,
        document_id: uuid.UUID,
        concept_id: uuid.UUID,
        query_text: str,
        n_results: int = 5,
    ) -> str:
        vs = self._chroma_vector_store(document_id)
        embed_model = self._embed_model()
        index = VectorStoreIndex.from_vector_store(vs, embed_model=embed_model)
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="concept_id",
                    operator=FilterOperator.EQ,
                    value=str(concept_id),
                )
            ]
        )
        retriever = index.as_retriever(similarity_top_k=n_results, filters=filters)
        nodes = retriever.retrieve(query_text)
        parts = [n.get_content() for n in nodes if n.get_content()]
        return "\n\n".join(parts)

    def delete_document_collection(self, document_id: uuid.UUID) -> None:
        name = self._collection_name(document_id)
        try:
            self._raw_client.delete_collection(name)
        except Exception:
            pass
