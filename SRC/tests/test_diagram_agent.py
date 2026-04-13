from unittest.mock import patch

import pytest

from Pipelines.MermaidRenderer import render_mermaid_to_svg
from playwright._impl._errors import Error as PlaywrightError


@pytest.mark.asyncio
async def test_render_mermaid_to_svg_returns_none_on_failure_without_fallback():
    with patch("Pipelines.MermaidRenderer.sync_playwright", side_effect=RuntimeError("boom")):
        out = await render_mermaid_to_svg("flowchart TD\nA-->B")
    assert out is None


@pytest.mark.asyncio
async def test_render_mermaid_to_svg_uses_fallback_with_label():
    with patch("Pipelines.MermaidRenderer.sync_playwright", side_effect=RuntimeError("boom")):
        out = await render_mermaid_to_svg("flowchart TD\nA-->B", fallback_label="Concept")
    assert out is not None
    assert "<svg" in out


@pytest.mark.asyncio
async def test_render_mermaid_to_svg_returns_none_on_missing_playwright_browsers_without_fallback():
    missing_browser_error = PlaywrightError(
        "BrowserType.launch: Executable doesn't exist at C:\\Users\\Ayman\\AppData\\Local\\ms-playwright\\chromium\\chrome.exe"
    )
    with patch("Pipelines.MermaidRenderer.sync_playwright", side_effect=missing_browser_error):
        out = await render_mermaid_to_svg("flowchart TD\nA-->B")
    assert out is None
