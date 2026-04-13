import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jinja2

from Models.Session import Turn
from Stats.Metrics import PDF_GENERATION_LATENCY
from config import get_settings

logger = logging.getLogger(__name__)


class ReportComposer:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._root = Path(__file__).resolve().parent.parent
        self._template_dir = (self._root / self._settings.report_template_dir).resolve()
        self._output_dir = (self._root / self._settings.report_output_dir).resolve()

    async def compose(
        self,
        *,
        session_id: uuid.UUID,
        concept_name: str,
        state_snapshot: dict,
        analyst: dict,
        turns: list[Turn],
        diagram_svg: str,
        ideal_answer: str,
    ) -> str:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self._template_dir)),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
        )
        template = env.get_template("session_report.html")
        ctx = {
            "session": {
                "session_id": str(session_id),
                "topic": concept_name,
                "name": state_snapshot.get("session_name") or concept_name,
            },
            "generated_at": datetime.now(timezone.utc).strftime("%b %d, %Y"),
            "summary": {
                "probe_turns": int(state_snapshot.get("probe_turns") or 0),
                "self_rating": state_snapshot.get("self_rating"),
                "classifier_confidence": float(state_snapshot.get("last_classifier_confidence") or 0.0),
                "overall": analyst.get("overall_performance", "developing"),
            },
            "analyst": analyst,
            "turns": [
                {
                    "student_input": t.student_input,
                    "question": t.question_generated,
                    "classifier_state": t.classifier_state,
                    "clarification": t.clarification,
                    "diagram_svg": t.diagram_svg,
                }
                for t in turns
            ],
            "concept_diagram_svg": diagram_svg,
            "model_answer": ideal_answer,
            "review_schedule": [],
        }
        html_str = template.render(**ctx)
        out_path = self._output_dir / f"{session_id}.pdf"
        css_path = self._template_dir / "style.css"
        t0 = time.perf_counter()

        try:
            from weasyprint import CSS, HTML
        except OSError as e:
            logger.warning("WeasyPrint unavailable (%s); writing HTML fallback for session=%s", e, session_id)
            html_path = self._output_dir / f"{session_id}.html"
            html_path.write_text(html_str, encoding="utf-8")
            PDF_GENERATION_LATENCY.observe(time.perf_counter() - t0)
            return str(html_path)

        stylesheets = [CSS(filename=str(css_path))] if css_path.is_file() else []

        def _write() -> None:
            HTML(string=html_str, base_url=str(self._template_dir)).write_pdf(
                str(out_path),
                stylesheets=stylesheets,
            )

        try:
            await asyncio.wait_for(
                asyncio.to_thread(_write),
                timeout=self._settings.pdf_generation_timeout_seconds,
            )
        except Exception:
            logger.exception("WeasyPrint PDF failed session=%s", session_id)
            html_path = self._output_dir / f"{session_id}.html"
            html_path.write_text(html_str, encoding="utf-8")
            PDF_GENERATION_LATENCY.observe(time.perf_counter() - t0)
            return str(html_path)
        PDF_GENERATION_LATENCY.observe(time.perf_counter() - t0)
        return str(out_path)
