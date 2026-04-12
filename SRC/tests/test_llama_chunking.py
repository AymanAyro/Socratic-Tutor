"""Contract: LlamaIndex SentenceSplitter produces nodes with propagated metadata."""

import uuid

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter


def test_sentence_splitter_propagates_concept_metadata():
    cid = str(uuid.uuid4())
    doc = Document(text="Paragraph one.\n\nParagraph two.\n\n" * 50, metadata={"concept_id": cid})
    splitter = SentenceSplitter(chunk_size=900, chunk_overlap=120)
    nodes = splitter.get_nodes_from_documents([doc])
    assert len(nodes) >= 1
    for n in nodes:
        assert n.metadata.get("concept_id") == cid
