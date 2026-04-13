"""Test defaults: avoid Postgres LangGraph checkpointer when CI has no DB."""

import os

os.environ.setdefault("LANGGRAPH_CHECKPOINT_BACKEND", "memory")
