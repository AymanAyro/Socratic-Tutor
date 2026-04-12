"""Contract: retrieval filters match stored node metadata (`concept_id` on `MetadataFilters`)."""

import uuid

from llama_index.core.vector_stores.types import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)


def test_concept_id_metadata_filter_matches_vector_store_contract():
    cid = str(uuid.uuid4())
    filters = MetadataFilters(
        filters=[
            MetadataFilter(
                key="concept_id",
                operator=FilterOperator.EQ,
                value=cid,
            )
        ]
    )
    assert len(filters.filters) == 1
    flt = filters.filters[0]
    assert flt.key == "concept_id"
    assert flt.operator == FilterOperator.EQ
    assert flt.value == cid
