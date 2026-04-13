import logging
import time

from playwright.async_api import async_playwright

from Stats.Metrics import DIAGRAM_RENDER_LATENCY
from config import get_settings

logger = logging.getLogger(__name__)

MERMAID_HTML_PREFIX = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
  mermaid.initialize({ startOnLoad: true, theme: "neutral" });
</script>
</head><body>
<pre class="mermaid">"""

MERMAID_HTML_SUFFIX = """</pre>
</body></html>"""


def fallback_diagram_svg(concept_name: str) -> str:
    label = (concept_name or "Concept").strip()[:48]
    return f"""
<svg viewBox="0 0 200 80" xmlns="http://www.w3.org/2000/svg">
  <rect x="10" y="10" width="180" height="60" rx="8" fill="#1a1a22" stroke="#7c6af7" stroke-width="1"/>
  <text x="100" y="45" text-anchor="middle" font-size="13" font-family="system-ui" fill="#9898b0">{label}</text>
</svg>
""".strip()


async def render_mermaid_to_svg(mermaid_code: str, fallback_label: str | None = None) -> str | None:
    settings = get_settings()
    t0 = time.perf_counter()
    safe = (mermaid_code or "").replace("</script>", "<\\/script>")
    html = MERMAID_HTML_PREFIX + safe + MERMAID_HTML_SUFFIX
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_content(html, timeout=int(settings.mermaid_render_timeout_seconds * 1000))
                await page.wait_for_selector("svg", timeout=int(settings.mermaid_render_timeout_seconds * 1000))
                svg = await page.inner_html("svg")
            finally:
                await browser.close()
        DIAGRAM_RENDER_LATENCY.observe(time.perf_counter() - t0)
        return svg or None
    except Exception:
        logger.exception("Mermaid render failed")
        DIAGRAM_RENDER_LATENCY.observe(time.perf_counter() - t0)
        if fallback_label:
            return fallback_diagram_svg(fallback_label)
        return None
