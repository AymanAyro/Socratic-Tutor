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


async def render_mermaid_to_svg(mermaid_code: str) -> str:
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
        return svg or ""
    except Exception:
        logger.exception("Mermaid render failed")
        DIAGRAM_RENDER_LATENCY.observe(time.perf_counter() - t0)
        raise
