# Socratic Tutor — Cursor Agent Task Spec
> Covers four areas: session flow bug, phase UX clarity, concept diagrams, and report redesign.
> Read `socratic_tutor_project.md` and `socratic_tutor_stage2.md` first for full context.
> Work through each section in order — later sections depend on earlier fixes.

---

## 0. Orientation — Read These Files First

Before touching any code, read these files in full:

```
SRC/Engine/edges.py
SRC/Engine/nodes.py
SRC/Engine/state.py
SRC/Engine/graph.py
SRC/Routes/Session.py
frontend/src/pages/TutorPage.tsx
frontend/src/components/chat/
frontend/src/api/
```

And for the report:
```
SRC/Pipelines/ReportComposer.py
SRC/templates/report/session_report.html
SRC/templates/report/style.css
SRC/Engine/agents/PerformanceAnalyst.py
```

---

## 1. Bug — Session Flow: "End & Report" Triggers CONSOLIDATE Instead of SESSION_END

### Symptom
Clicking the "End & Report" button skips to CONSOLIDATE phase instead of going directly
to report generation and download. The student is stuck in a loop they never asked for.

### Root cause — check these two things

**A. Edge routing in `SRC/Engine/edges.py`**

The `route_after_consolidate` function likely has a logic error where it always returns
`"consolidate"` on a retry condition even when triggered by an explicit end request.
There is also no explicit handling for a user-initiated end signal. Look for something like:

```python
def route_after_consolidate(state: SessionState) -> str:
    last_state = state["current_concept"].classifier_states[-1]
    ...
    return "consolidate"    # this may fire when it should go to "report"
```

**B. The frontend "End & Report" button call in `frontend/src/pages/TutorPage.tsx`**

The button likely calls `POST /api/v1/session/{id}/end` but the backend handler may be
routing through the `consolidate` node instead of jumping directly to `report`.

### Fix

**In `SRC/Engine/edges.py`**, add an `end_requested` flag check before all other conditions:

```python
def route_probe(state: SessionState) -> str:
    # MUST be checked first — user explicitly requested end
    if state.get("end_requested"):
        return "report"
    concept = state["current_concept"]
    if concept.mastery_signal:
        return "reveal"
    if concept.probe_turns >= concept.max_probe_turns:
        return "reveal"
    if state["messages"] and state["messages"][-1].content.strip() == "/reveal":
        return "reveal"
    return "probe"

def route_after_consolidate(state: SessionState) -> str:
    # MUST be checked first
    if state.get("end_requested"):
        return "report"
    last_states = state["current_concept"].classifier_states
    last_state = last_states[-1] if last_states else "stuck"
    remaining = state["concept_queue"]
    consolidation_attempts = state.get("consolidation_attempts", 0)
    if last_state in ("correct", "partial"):
        return "next_concept" if remaining else "report"
    if consolidation_attempts >= 1:          # only one retry, then move on
        return "next_concept" if remaining else "report"
    return "consolidate"
```

**In `SRC/Engine/state.py`**, add the new fields to `SessionState`:

```python
class SessionState(TypedDict):
    ...
    end_requested: bool          # set True by /session/{id}/end handler
    consolidation_attempts: int  # tracks retries, initialise to 0
    ...
```

**In `SRC/Routes/Session.py`**, the `end` endpoint must write `end_requested: True` into
graph state before invoking the graph, not just trigger a separate code path:

```python
@router.post("/{session_id}/end")
async def end_session(session_id: str, ...):
    await graph.aupdate_state(
        config={"configurable": {"thread_id": session_id}},
        values={"end_requested": True}
    )
    # Then invoke the graph one more step so it routes to "report"
    result = await graph.ainvoke(None, config={"configurable": {"thread_id": session_id}})
    return {"report_status": "generating", "session_id": session_id}
```

**In `SRC/Engine/nodes.py`**, make sure `consolidate_node` increments the counter:

```python
async def consolidate_node(state: SessionState, ...) -> dict:
    ...
    return {
        ...,
        "consolidation_attempts": state.get("consolidation_attempts", 0) + 1
    }
```

**In `frontend/src/pages/TutorPage.tsx`**, after the end API call resolves, navigate to
the report page — do not leave the user on the chat screen:

```tsx
const handleEndSession = async () => {
  setIsEnding(true);
  await api.endSession(sessionId);
  navigate(`/report/${sessionId}`);   // go immediately to report status page
};
```

---

## 2. UX — Phase Visibility: The Student Should Always Know Where They Are

### Problem
The user has no idea what "probe", "consolidate", or "end" mean. These are internal
engine terms leaking into the UI. The session flow needs a clear, human-readable
progress indicator.

### What to build

Add a `SessionPhaseBar` component. It lives at the top of the chat interface and shows
the current phase in plain language with a progress indicator.

**File:** `frontend/src/components/chat/SessionPhaseBar.tsx`

```tsx
// Props come from the session state — phase is one of:
// "PROBE" | "REVEAL" | "REFLECT" | "CONSOLIDATE" | "END"

const PHASE_CONFIG = {
  PROBE: {
    label: "Exploration",
    description: "Answer the tutor's questions in your own words",
    color: "blue",
  },
  REVEAL: {
    label: "Reveal",
    description: "See the full explanation and concept diagram",
    color: "green",
  },
  REFLECT: {
    label: "Reflect",
    description: "Rate how well you understood this concept",
    color: "yellow",
  },
  CONSOLIDATE: {
    label: "Check",
    description: "One final question to confirm it landed",
    color: "orange",
  },
  END: {
    label: "Done",
    description: "Session complete — your report is ready",
    color: "purple",
  },
};
```

The bar should also show the turn counter during PROBE: `"Question 2 of 5"`.
The turn count comes from `GET /api/v1/session/{id}/phase` which returns
`{ phase, probe_turns, max_probe_turns }`.

Render the phase steps as a horizontal stepper (not a dropdown, not a raw label).
Steps: Exploration → Reveal → Reflect → Check → Done. The active step is highlighted.
Completed steps show a checkmark. Future steps are greyed out.

**Wire it in** `frontend/src/pages/TutorPage.tsx` — fetch phase on mount and after each
turn, update the bar. The API call is already defined in the spec:
`GET /api/v1/session/{id}/phase`.

### Rename all user-facing strings

Search the entire `frontend/src/` directory for these strings and replace them:

| Find | Replace with |
|------|-------------|
| `"probe"` (displayed to user) | `"Exploration"` |
| `"consolidate"` (displayed to user) | `"Check"` |
| `"stuck"` (displayed to user) | `"Still working on it"` |
| `"End & Report"` button | `"Finish Session"` |
| `"partial"` (displayed to user) | `"Getting there"` |
| `"correct"` (displayed to user) | `"Got it"` |

These renames are **display-only** — do not change the values used in API calls or
state comparisons. Use a `DISPLAY_LABELS` map, not inline string replacement.

---

## 3. Diagrams — Generate and Show Concept Diagrams in Both Chat and Report

### Current state
`DiagramAgent.py` and `MermaidRenderer.py` exist in the spec but are either missing or
not hooked into the session graph. The `background_worker_node` in `nodes.py` is
supposed to fire `generate_concept_diagram` concurrently during PROBE, but the diagram
never appears in the REVEAL phase or the report.

### Backend tasks

**Step 1 — Verify `DiagramAgent.py` exists at `SRC/Engine/agents/DiagramAgent.py`.**
If it does not exist, create it using the prompt from `socratic_tutor_stage2.md`:

```python
DIAGRAM_SYSTEM = """
You are an educational diagram designer. Generate a Mermaid diagram that visually
explains the following concept to a student.

Rules:
- Use flowchart TD or graph LR — whichever fits the concept structure better
- Maximum 10 nodes. Every node label must be under 6 words.
- Show the mechanism, not a list: cause → effect, components → relationships, steps → order
- No title node. No legend nodes.
- Output only the raw Mermaid code. Nothing else.

Concept: {concept}
Description: {description}
"""

async def generate_concept_diagram(concept: ConceptState, llm) -> str:
    """Returns raw Mermaid string."""
    prompt = DIAGRAM_SYSTEM.format(
        concept=concept.name,
        description=concept.description if hasattr(concept, "description") else ""
    )
    result = await llm.ainvoke([HumanMessage(content=prompt)])
    return result.content.strip()
```

**Step 2 — Verify `MermaidRenderer.py` exists at `SRC/Pipelines/MermaidRenderer.py`.**
If it does not exist, create it:

```python
from playwright.async_api import async_playwright

MERMAID_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <script>mermaid.initialize({{ startOnLoad: true }});</script>
</head>
<body>
  <div class="mermaid">{code}</div>
</body>
</html>
"""

async def render_mermaid_to_svg(mermaid_code: str, timeout_seconds: int = 10) -> str | None:
    """
    Returns SVG string or None on failure.
    Never raises — diagram failures must not block REVEAL.
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(
                MERMAID_HTML_TEMPLATE.format(code=mermaid_code),
                wait_until="networkidle"
            )
            await page.wait_for_selector("svg", timeout=timeout_seconds * 1000)
            svg = await page.inner_html("svg")
            await browser.close()
            return svg
    except Exception as e:
        # Log but never re-raise — diagram is enhancement, not requirement
        print(f"[MermaidRenderer] render failed: {e}")
        return None
```

**Step 3 — Hook into `background_worker_node` in `SRC/Engine/nodes.py`.**

Make sure both `ideal_answer` and `concept_diagram_svg` are set concurrently:

```python
async def background_worker_node(state: SessionState, config) -> dict:
    concept = state["current_concept"]
    llm = get_llm("generator")

    ideal_answer_task = generate_ideal_answer(concept, llm)
    diagram_task = generate_concept_diagram(concept, llm)

    ideal_answer, mermaid_code = await asyncio.gather(
        ideal_answer_task, diagram_task
    )
    diagram_svg = await render_mermaid_to_svg(mermaid_code)   # None on failure

    return {
        "current_concept": concept.model_copy(update={
            "ideal_answer": ideal_answer,
            "concept_diagram_svg": diagram_svg     # None is valid — frontend handles it
        })
    }
```

**Step 4 — Add `GET /api/v1/session/{id}/diagram/{concept_id}` endpoint.**
This endpoint returns the SVG for a concept. It reads from the LangGraph checkpointed
state, finds the matching concept, and returns the SVG string.

```python
@router.get("/{session_id}/diagram/{concept_id}")
async def get_concept_diagram(session_id: str, concept_id: str):
    state = await graph.aget_state(
        config={"configurable": {"thread_id": session_id}}
    )
    for concept in state.values.get("concept_queue", []):
        if concept.concept_id == concept_id and concept.concept_diagram_svg:
            return Response(
                content=concept.concept_diagram_svg,
                media_type="image/svg+xml"
            )
    raise HTTPException(404, "Diagram not ready or concept not found")
```

### Frontend tasks

**Step 5 — Build `RevealPanel.tsx` at `frontend/src/components/chat/RevealPanel.tsx`.**

This component renders when `phase === "REVEAL"`. It shows:
1. The ideal answer (streamed text, same SSE mechanism as questions)
2. The concept diagram (SVG rendered inline, with a loading skeleton while it loads)
3. A "Got it" button that advances to REFLECT

```tsx
// RevealPanel.tsx

// Fetch diagram from GET /api/v1/session/{id}/diagram/{concept_id}
// Show a skeleton box while loading (use CSS animation, not a spinner)
// If diagram is null/404, show a subtle "Diagram unavailable" text — do not crash

// For the ideal answer: it comes in the SSE stream from /session/{id}/turn
// The reveal payload has type: "reveal" with fields: ideal_answer, concept_diagram_svg
// Wire up the existing SSE handler in TutorPage.tsx to detect type === "reveal"
// and render RevealPanel instead of a chat bubble
```

Key SSE handling change in `frontend/src/pages/TutorPage.tsx`:

```tsx
// In the SSE message handler:
if (parsedData.type === "reveal") {
  setPhase("REVEAL");
  setRevealContent({
    idealAnswer: parsedData.ideal_answer,
    diagramSvg: parsedData.concept_diagram_svg,   // may be null
    conceptId: parsedData.concept_id,
  });
} else {
  // existing chat bubble handling
}
```

**Step 6 — Handle the diagram poll for race condition.**

If the background worker hasn't finished when REVEAL triggers (student answered very
quickly), the diagram will be null. In `RevealPanel.tsx`, if `diagramSvg` is null,
poll `GET /api/v1/session/{id}/diagram/{concept_id}` every 1000ms for up to 10 seconds.
Show "Building your concept diagram..." skeleton during the wait.
After 10 seconds with no result, show "Diagram unavailable" and stop polling.

---

## 4. Report — Full Redesign

### Current problems (verified from the uploaded session report)
- The report is a single paragraph of static text in the "model answer" section — it
  is not generated from the session; it is the concept's pre-written description
- No concept diagram embedded per concept
- No per-question dialogue breakdown (the HTML has it but only shows the raw question text,
  not the model answer or diagram for that concept)
- The "Understanding journey" dots don't link to the specific turn cards
- The "AI insight" is present but one-line generic
- No mastery sparklines
- No next review schedule
- Recommendations are generic (not derived from this student's specific pattern)
- The report is not a downloadable PDF — it is saved as an HTML file locally

### Backend tasks

**Step 7 — Fix `PerformanceAnalyst.py`.**

Verify the prompt in `SRC/Engine/agents/PerformanceAnalyst.py` matches the spec in
`socratic_tutor_stage2.md`. The output JSON must contain:

```json
{
  "overall_performance": "struggling | developing | solid | strong",
  "strongest_concept": "string",
  "weakest_concept": "string",
  "insight": "2-3 sentence personalised observation",
  "recommendations": ["3 specific actionable items"],
  "dunning_kruger_flag": true,
  "concepts_to_review": ["concept_ids"]
}
```

If `dunning_kruger_flag` is true (self_rating >> classifier confidence), the insight
must mention this explicitly in plain language. Add this to the analyst prompt:

```
If the student's self-rating is 2 or more points higher than the classifier confidence
score suggests, set dunning_kruger_flag to true and include in the insight that the
student tends to overestimate their understanding — phrase this constructively.
```

**Step 8 — Rewrite `SRC/templates/report/session_report.html`.**

Replace the current template entirely. The new structure (Jinja2):

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Session Report — {{ session.concept_name }}</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>

<!-- HEADER -->
<header class="report-header">
  <div class="brand">Socratic Tutor</div>
  <div class="meta">
    <h1>Session Report</h1>
    <p class="subtitle">{{ session.concept_name }} · {{ session.date }}</p>
    <p class="session-id">Session {{ session.session_id[:8] }}</p>
  </div>
</header>

<!-- PERFORMANCE OVERVIEW (keep existing metric-grid, add overall badge) -->
<section class="section">
  <h2>Performance Overview</h2>
  <div class="metric-grid">
    <div class="metric-card">
      <span class="metric-value">{{ stats.probe_turns }}</span>
      <span class="metric-label">Exploration turns</span>
    </div>
    <div class="metric-card">
      <span class="metric-value">{{ session.self_rating }} / 5</span>
      <span class="metric-label">Your self-rating</span>
    </div>
    <div class="metric-card">
      <span class="metric-value">{{ "%.0f"|format(stats.classifier_confidence * 100) }}%</span>
      <span class="metric-label">Assessed confidence</span>
    </div>
    <div class="metric-card metric-card--highlight">
      <span class="metric-value">{{ analyst.overall_performance }}</span>
      <span class="metric-label">Overall</span>
    </div>
  </div>
  {% if analyst.dunning_kruger_flag %}
  <div class="alert alert--yellow">
    ⚠ Your self-rating was notably higher than your responses indicated.
    See the AI insight below.
  </div>
  {% endif %}
</section>

<!-- UNDERSTANDING JOURNEY (existing timeline dots — keep them) -->
<section class="section">
  <h2>Understanding Journey</h2>
  <div class="turn-timeline">
    {% for turn in turns %}
    <a href="#turn-{{ loop.index }}" class="timeline-dot timeline-dot--{{ turn.classifier_state }}">
      <span class="dot-number">{{ loop.index }}</span>
      <span class="dot-label">{{ DISPLAY_LABELS[turn.classifier_state] }}</span>
    </a>
    {% endfor %}
  </div>
</section>

<!-- CONCEPT EXPLANATION (replaces the static paragraph) -->
<section class="section section--reveal">
  <h2>Concept Explanation</h2>
  <div class="reveal-grid">
    <div class="reveal-answer">
      <h3>Model Answer</h3>
      <p>{{ current_concept.ideal_answer }}</p>
    </div>
    {% if current_concept.concept_diagram_svg %}
    <div class="reveal-diagram">
      <h3>Concept Diagram</h3>
      <div class="diagram-container">
        {{ current_concept.concept_diagram_svg | safe }}
      </div>
    </div>
    {% endif %}
  </div>
</section>

<!-- DIALOGUE BREAKDOWN (keep existing turn cards, add model answer reference) -->
<section class="section">
  <h2>Dialogue Breakdown</h2>
  {% for turn in turns %}
  <div id="turn-{{ loop.index }}" class="turn-card turn-card--{{ turn.classifier_state }}">
    <div class="turn-card-header">
      <span class="turn-number">Turn {{ loop.index }}</span>
      <span class="turn-badge turn-badge--{{ turn.classifier_state }}">
        {{ DISPLAY_LABELS[turn.classifier_state] }}
      </span>
      {% if turn.classifier_state == "stuck" %}
      <span class="turn-badge turn-badge--hint">Tutor simplified the question</span>
      {% endif %}
    </div>
    <div class="turn-student">
      <span class="turn-role">Your answer</span>
      <p>{{ turn.student_input }}</p>
    </div>
    <div class="turn-tutor">
      <span class="turn-role">Tutor's next question</span>
      <p class="turn-question">{{ turn.question_generated }}</p>
    </div>
    {% if turn.gap %}
    <div class="turn-gap">
      <span class="turn-role">What was missing</span>
      <p>{{ turn.gap }}</p>
    </div>
    {% endif %}
  </div>
  {% endfor %}
</section>

<!-- AI INSIGHT -->
<section class="section">
  <h2>AI Insight</h2>
  <div class="insight-callout">
    <p>{{ analyst.insight }}</p>
  </div>
</section>

<!-- RECOMMENDATIONS -->
<section class="section">
  <h2>Recommendations</h2>
  <div class="reco-grid">
    {% for reco in analyst.recommendations %}
    <div class="reco-card">
      <span class="reco-number">{{ loop.index }}</span>
      <p>{{ reco }}</p>
    </div>
    {% endfor %}
  </div>
</section>

<!-- NEXT REVIEW SCHEDULE (new section) -->
<section class="section">
  <h2>Next Review Schedule</h2>
  <div class="review-schedule">
    {% for item in review_schedule %}
    <div class="review-item">
      <span class="review-concept">{{ item.concept_name }}</span>
      <span class="review-date">Review in {{ item.days_until }} days
        ({{ item.review_date }})</span>
      <div class="mastery-bar">
        <div class="mastery-fill" style="width: {{ item.mastery_score * 100 }}%"></div>
      </div>
    </div>
    {% endfor %}
  </div>
</section>

</body>
</html>
```

**Step 9 — Update `SRC/Pipelines/ReportComposer.py`.**

The `compose` method must pass all the new context variables to the template:

```python
async def compose(self, state: SessionState, analyst: AnalystOutput) -> str:
    current_concept = state["current_concept"]
    turns = [
        msg for msg in state["messages"]
        # filter to only turn objects with classifier metadata
        # turns are stored in the session's TURNS table, not just messages
    ]
    # Fetch actual Turn records from DB for full metadata (gap, classifier_state, etc.)
    db_turns = await fetch_turns_for_session(state["session_id"])
    review_schedule = await build_review_schedule(
        state["user_id"], [current_concept.concept_id]
    )
    context = {
        "session": state,
        "current_concept": current_concept,
        "turns": db_turns,
        "analyst": analyst,
        "stats": {
            "probe_turns": current_concept.probe_turns,
            "classifier_confidence": _avg_confidence(db_turns),
        },
        "review_schedule": review_schedule,
        "DISPLAY_LABELS": {
            "correct": "Got it",
            "partial": "Getting there",
            "wrong": "Incorrect",
            "stuck": "Still working on it",
        }
    }
    html_str = self.jinja.get_template("session_report.html").render(**context)
    output_path = f"reports/{state['session_id']}.pdf"
    await asyncio.to_thread(
        lambda: HTML(string=html_str).write_pdf(
            output_path,
            stylesheets=[CSS(filename="templates/report/style.css")]
        )
    )
    return output_path
```

**Step 10 — Rewrite `SRC/templates/report/style.css`.**

The current style.css is referenced from a local Windows path (`file:///C:/Users/...`)
which breaks when the report is served. Fix the CSS reference in the template — use a
relative path or embed styles inline in the HTML template.

Key CSS additions needed:
- `.reveal-grid` — two-column layout (answer left, diagram right), collapses to single
  column for narrow PDF pages
- `.diagram-container svg` — max-width 100%, height auto, border-radius 8px
- `.mastery-bar` — thin progress bar, `.mastery-fill` filled with `var(--color-accent)`
- `.review-schedule` — clean list layout with concept name and date aligned left/right
- `.turn-gap` — subtle callout box in amber/yellow inside the turn card
- `.alert--yellow` — yellow warning banner for dunning-kruger flag
- All styles must use print-safe units (pt/mm for sizing where relevant)
- Remove the `file:///` path from the `<link rel="stylesheet">` in the HTML template

### Frontend tasks

**Step 11 — Build a Report page at `frontend/src/pages/ReportPage.tsx`.**

This page:
1. Shows on `/report/:sessionId`
2. Polls `GET /api/v1/report/{sessionId}/status` every 2 seconds while status is
   `"generating"`. Shows a loading state: "Generating your session report..."
3. When status is `"ready"`, shows a "Download Report" button that hits
   `GET /api/v1/report/{sessionId}/pdf` and triggers a browser download
4. Also renders an inline HTML preview of the report content (without the PDF overhead)
   by calling a new endpoint `GET /api/v1/report/{sessionId}/summary` that returns
   the analyst JSON so you can render the insight, recommendations, and review schedule
   directly in the React page — the student gets immediate feedback without waiting
   for the full PDF

**Step 12 — Add `GET /api/v1/report/{session_id}/summary` to `SRC/Routes/Session.py`**
(or create `SRC/Routes/Report.py` as the spec describes):

```python
@router.get("/{session_id}/summary")
async def get_report_summary(session_id: str):
    """
    Returns the analyst output JSON immediately after consolidation ends.
    This is fast (analyst already ran during report_node).
    Used by the frontend to show inline results without waiting for PDF.
    """
    # Fetch from the graph state or a reports table in PostgreSQL
    ...
```

---

## 5. Acceptance Criteria

### 5.1 Session flow
- [ ] Pressing "Finish Session" ends the session cleanly and navigates to `/report/:id`
- [ ] It never incorrectly triggers CONSOLIDATE
- [ ] CONSOLIDATE only runs once during normal flow (after REFLECT), with max one retry
- [ ] PROBE exits to REVEAL when turn limit is hit, mastery is signalled, or `/reveal` is typed

### 5.2 Phase UX
- [ ] A horizontal stepper is visible at the top of the chat showing: Exploration → Reveal
      → Reflect → Check → Done
- [ ] Active step is highlighted, completed steps show a checkmark
- [ ] During Exploration, the stepper subtitle shows "Question N of M"
- [ ] No internal engine terms (probe, consolidate, stuck, partial, correct) are visible
      to the student anywhere in the UI

### 5.3 Diagrams
- [ ] During PROBE, `background_worker_node` runs concurrently and populates
      `concept_diagram_svg` in the session state
- [ ] When REVEAL fires, the SSE payload includes both `ideal_answer` and `concept_diagram_svg`
- [ ] The frontend renders the SVG diagram inline in the RevealPanel
- [ ] If the diagram is null (render failed or worker still running), a skeleton loads
      and polls for up to 10 seconds, then shows "Diagram unavailable" gracefully
- [ ] The diagram is embedded in the PDF report's per-concept section

### 5.4 Report
- [ ] Report contains: performance overview, understanding journey, concept explanation
      (with model answer + diagram), full dialogue breakdown with `gap` per turn,
      AI insight (personalised, not generic), 3 specific recommendations,
      next review schedule with mastery bars
- [ ] If `dunning_kruger_flag` is true, a visible yellow alert appears at the top
- [ ] All turn badges use human-readable labels (not "stuck", "partial", etc.)
- [ ] The CSS link in the HTML template uses a relative path, not `file:///`
- [ ] PDF downloads correctly from `GET /api/v1/report/{session_id}/pdf`
- [ ] ReportPage at `/report/:id` shows inline summary immediately and a download button

---

## 6. Do Not Touch

- `SRC/Stats/` — Prometheus metrics are working, leave them alone
- `SRC/Pipelines/SpacedRepetition.py` — SM-2 logic is correct
- `SRC/Stores/LLM/PromptRegistry.py` — prompt versioning is correct
- `Docker/` — infra config is correct
- `Eval/` — eval harness is correct
- `.github/workflows/` — CI is correct

---

## 7. Testing Checklist (run after each section)

```bash
# After section 1 (flow bug fix):
cd SRC && uv run pytest tests/test_session_flow.py -v

# After section 3 (diagrams):
cd SRC && uv run pytest tests/test_diagram_agent.py -v
# Manually: start a session, answer 3 turns, check that /session/{id}/diagram/{concept_id}
# returns a 200 with SVG content

# After section 4 (report):
cd SRC && uv run pytest tests/test_report_composer.py -v
# Manually: end a session, check /report/{id}/status becomes "ready",
# download PDF and verify all sections are present

# Full integration smoke test:
cd SRC && uv run pytest tests/ -v -k "not eval"
```

If any of these test files don't exist yet, create them as part of the work.
