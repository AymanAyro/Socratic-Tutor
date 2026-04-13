from unittest.mock import patch

import pytest

from Pipelines.MermaidRenderer import render_mermaid_to_svg


@pytest.mark.asyncio
async def test_render_mermaid_to_svg_returns_none_on_failure_without_fallback():
    with patch("Pipelines.MermaidRenderer.async_playwright", side_effect=RuntimeError("boom")):
        out = await render_mermaid_to_svg("flowchart TD\nA-->B")
    assert out is None


@pytest.mark.asyncio
async def test_render_mermaid_to_svg_uses_fallback_with_label():
    with patch("Pipelines.MermaidRenderer.async_playwright", side_effect=RuntimeError("boom")):
        out = await render_mermaid_to_svg("flowchart TD\nA-->B", fallback_label="Concept")
    assert out is not None
    assert "<svg" in out
