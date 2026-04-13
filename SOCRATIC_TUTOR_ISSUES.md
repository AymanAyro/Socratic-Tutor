# Socratic Tutor — Full Issues & Implementation Backlog

> Generated from code review, UI screenshots, session transcript, and session report HTML.
> Organized by domain. Every item is actionable for Cursor.

---

## 1. PEDAGOGICAL QUALITY (Core Teaching Logic)

### 1.1 Book ingestion is too shallow
**Problem:** A 991-page book is distilled to ~10 surface-level concept names and a single paragraph each. Students learn nothing from the material itself — they get ~100 words of context per topic.  
**Fix:**
- During ingestion, chunk the PDF into overlapping passages (e.g. 512-token chunks, 64-token overlap).
- Store chunks in a vector DB (e.g. ChromaDB, Supabase pgvector).
- At session start, retrieve the top-K most relevant chunks for the chosen concept using semantic search.
- Feed those retrieved chunks to the tutor system prompt as grounding context so questions and revealed answers are rich and sourced from the actual book.

### 1.2 Tutor capitulates too easily
**Problem:** When the student says "I don't know" or "Tell me," the tutor immediately scaffolds down and gives a hint — it should push back with another angle first.  
**Fix:**  
- Add a rule in the system prompt: if the student says "I don't know," "tell me," "idk," or any surrender phrase, the tutor must attempt **at least one rephrasing or concrete analogy** before giving a hint.
- Only after two consecutive surrenders should the tutor provide a partial hint (never the full answer).
- Track `surrenderStreak` per turn. Reset on any substantive student answer.

### 1.3 Answer quality grading is binary and too harsh
**Problem:** Turn 2 ("It'd struggle on doing so") is graded "Still working on it" — it is semantically correct (catastrophic forgetting). A student shouldn't be penalized for informal phrasing.  
**Fix:**  
- Grade answers on a 3-axis rubric: **accuracy**, **depth**, and **vocabulary**. A correct-but-informal answer should be "Getting there," not "Stuck."
- Include this rubric in the grader prompt so the LLM doesn't over-penalize casual but correct responses.

### 1.4 No scaffolded learning path
**Problem:** Questions jump from definition → edge cases → internals with no warm-up. Students who don't know the topic well are immediately lost.  
**Fix:**  
- Implement a `difficultyLevel` state: `[recall, comprehension, application, analysis]`.
- Start every session at `recall`. Promote only after two consecutive "Got it" turns.
- Demote one level after two consecutive "Stuck" turns.
- Track this in session state and pass it to the tutor system prompt each turn.

### 1.5 Session ends without real consolidation
**Problem:** After the Socratic phase, the tutor reveals the full answer and then immediately asks a new question. The student's final answer ("I get it") triggers another drill question. There is no moment of synthesis.  
**Fix:**  
- After revealing the model answer, ask exactly **one** consolidation question that requires the student to restate the concept in their own words.
- Grade that restatement. If passing → mark session complete with "Mastered." If not → queue concept for review in 2 days.
- Only then end the session.

### 1.6 Self-rating mismatch is detected but not acted on in real-time
**Problem:** The discrepancy between the student's 5/5 self-rating and actual performance is only flagged in the post-session report. The student gets no real-time nudge.  
**Fix:**  
- After session ends (or mid-session at turn 5 if still stuck), display an in-app inline warning: *"You've marked yourself 5/5 but responses so far suggest a gap. Adjusting review schedule."*
- Auto-override the mastery score used for spaced-repetition scheduling when discrepancy > 2 points.

---

## 2. DIAGRAM GENERATION (Background Agent)

### 2.1 Diagrams are never generated — root cause unknown
**Problem:** Diagrams are expected in the session report but never appear. No error is surfaced to the user.  
**Fix:**  
- Add `try/catch` around every diagram generation call and log the full error to the console **and** to a visible debug panel in dev mode.
- Check if the diagram API key / model call is correctly configured and returning a response before attempting to render.
- Add a fallback: if diagram generation fails, show a placeholder card saying "Diagram unavailable" instead of silently omitting it.

### 2.2 Add per-turn diagram + correct answer to session report
**Problem:** Each turn in the report only shows: student answer + tutor's next question. The correct answer and a diagram are missing entirely.  
**Fix:**  
- After each tutor turn completes, fire a **background agent call** (non-blocking) with this prompt:  
  ```
  Given this tutor question: "{question}"
  And this correct answer: "{modelAnswer}"
  Generate:
  1. A concise correct answer (2-4 sentences).
  2. A Mermaid.js or SVG diagram that visually explains the concept.
  Return JSON: { "correctAnswer": "...", "diagram": "..." }
  ```
- Store the result against the turn in the session record.
- Render in the report as: **Your answer → Correct answer → Diagram**.

### 2.3 Diagram type should match concept type
**Fix:**  
- If the question is about a process (e.g. backpropagation, fine-tuning steps) → use a **flowchart**.
- If it's about a comparison (e.g. PEFT vs full fine-tuning) → use a **comparison table or side-by-side diagram**.
- If it's about a hierarchy (e.g. model layers) → use a **tree diagram**.
- Pass the concept type to the diagram generation prompt so it picks the right format.

---

## 3. SESSION REPORT — Design Overhaul

### 3.1 Report has no CSS / design system
**Problem:** Image 4 shows the raw HTML renders completely unstyled — just plain black text on white. The `style.css` link is broken or missing.  
**Fix:**  
- Embed all styles inline in the generated HTML (do not rely on an external `style.css` that may not be present when the file is opened standalone).
- Or ensure `style.css` is bundled alongside the HTML when the report is exported/downloaded.

### 3.2 Report visual hierarchy is flat
**Fix — redesign the report HTML with these sections styled as cards:**
- **Header:** Brand name + session title + date in a colored banner (use `#6C63FF` as primary).
- **Performance Overview:** 4 metric cards in a 2×2 grid. Use color coding: green = good, amber = partial, red = struggling.
- **Understanding Journey:** Replace the plain link list with a horizontal dot timeline. Color-code dots: green (Got it), amber (Getting there), red (Stuck). Add connecting line between dots.
- **Dialogue Breakdown:** Each turn is a styled card with left-border color based on status. Inside: student answer in a speech bubble, correct answer in a highlighted box, diagram below.
- **AI Insight:** Amber alert card with icon.
- **Recommendations:** Numbered cards with icon per item.
- **Spaced Repetition Schedule:** Progress bar with mastery percentage and next review date.

### 3.3 Turn cards missing correct answer and diagram
**Fix:** See §2.2. Each turn card in the HTML should have three panels:
```
┌─────────────────────────────────────┐
│ Turn N  [Status badge]              │
│ ─────────────────────────────────── │
│ 💬 Your answer: "..."               │
│ ✅ Correct answer: "..."            │
│ 📊 [Diagram]                        │
│ ➡️  Tutor's follow-up: "..."        │
└─────────────────────────────────────┘
```

### 3.4 Typography is unreadable
**Fix:**
- Use `Inter` or `DM Sans` from Google Fonts (embed the `@import` in `<style>`).
- Base font: 15px, line-height: 1.7.
- Headings: `font-weight: 700`, clear size scale (h1: 28px, h2: 20px, h3: 16px).
- Body text color: `#1a1a2e`, not pure black.
- Background: `#f6f7fb`, not pure white.

---

## 4. DASHBOARD PAGE

### 4.1 Concept names show raw UUIDs
**Problem:** "Mastery by concept" section shows `122547c0...` and `a0cab4bb...` instead of human-readable concept names like "Fine-tuning" or "Foundation Models."  
**Fix:**  
- When storing mastery records, always write both `conceptId` (UUID) and `conceptName` (string).
- In the dashboard query, join or map `conceptId → conceptName` before rendering.
- If legacy records lack a name, fall back to looking up the concept name from the concepts table by ID.

### 4.2 Session cards show no useful information
**Problem:** Session cards only show: title, date, turn count. No indication of performance, mastery change, or topic.  
**Fix — add to each session card:**
- Overall status badge (Struggling / Progressing / Mastered) with color.
- Mastery delta: e.g. "+0.05 mastery" or "↑ 12%."
- Concept name (not UUID).
- A mini spark-line of turn statuses (row of 5-10 colored dots).

### 4.3 "Due for review" section says "Nothing due today" even with low mastery
**Problem:** A concept with 20% mastery and a review date of today shows nothing in "Due for review." Either the query is wrong or the spaced-repetition scheduler isn't writing the due date correctly.  
**Fix:**  
- Audit the spaced-repetition write path: confirm `nextReviewDate` is being written to the DB after every session.
- Fix the dashboard query to compare `nextReviewDate <= today` and surface those concepts.
- Show concept name, mastery bar, and a "Review now" button per due item.

### 4.4 Dashboard shows learner UUID in plain sight
**Problem:** `Learner: e0170e36-4a02-4753-b961-093a8be84e83` is displayed prominently. This is an internal ID, meaningless to the user.  
**Fix:**  
- Remove the raw UUID from the dashboard UI entirely.
- If identification is needed, show the user's display name or email instead.

### 4.5 No summary statistics
**Fix — add to the top of the dashboard:**
- Total sessions completed.
- Total concepts studied.
- Average mastery across all concepts.
- Current learning streak (days).

---

## 5. CHAT UI — Tutor Tab

### 5.1 Words are colliding / sticking together
**Problem:** Tutor messages render as "general-purposemodel," "itis being fine-tuned," "toperform," etc. — spaces are missing.  
**Fix:**  
- Inspect the LLM response post-processing pipeline. If the response is being trimmed, split, or reassembled anywhere — that is likely stripping spaces.  
- Add a sanitization step after receiving the LLM response: `response.replace(/([a-z])([A-Z])/g, '$1 $2')` as a stopgap, but find the root cause.
- If using streaming, ensure chunks are concatenated correctly and not dropping the trailing space of each chunk.

### 5.2 User message bubble gradient is visually poor
**Problem:** The user's chat bubble uses a muddy purple-grey gradient that is hard to read and looks unfinished.  
**Fix:**  
- Replace with a clean solid color: `background: #6C63FF; color: #fff;` for the user bubble.
- Tutor bubble: `background: #fff; border: 1px solid #e8e8f0; color: #1a1a2e;`.
- Ensure `border-radius: 18px 18px 4px 18px` for user (tail bottom-right) and `18px 18px 18px 4px` for tutor (tail bottom-left).

### 5.3 No loading indicator when waiting for tutor response
**Problem:** After the user submits an answer, nothing happens visually until the response arrives. No spinner, no dots, no feedback.  
**Fix:**  
- Immediately after the user sends a message, render a "typing indicator" bubble in the tutor's position:
  ```html
  <div class="typing-indicator">
    <span></span><span></span><span></span>
  </div>
  ```
  Animate with CSS: three dots bouncing sequentially (`animation: bounce 1.2s infinite`).
- Remove the indicator once the response stream begins.
- Also disable the Send button and grey out the input during the pending state to prevent double-sends.

### 5.4 Send button has no disabled/loading state
**Fix:**  
- While awaiting a response: `button.disabled = true`, change label to a spinner icon or "…".
- Re-enable once response is complete.

### 5.5 Input field doesn't support multi-line answers
**Problem:** A single `<input type="text">` cuts off longer student answers visually.  
**Fix:**  
- Replace the input with a `<textarea>` that auto-grows (using `rows=1` + CSS `resize: none` + JS to expand on input).
- Submit on `Enter` (without Shift), newline on `Shift+Enter`.

### 5.6 No visual distinction between Socratic phase and reveal phase
**Problem:** When the tutor switches from asking questions to revealing the answer, there is no visual break. It feels like just another message.  
**Fix:**  
- When the tutor enters reveal mode, render a full-width divider: `── Concept Revealed ──` with a subtle background change.
- The revealed answer card should have a distinct style: left border `#22c55e`, background `#f0fdf4`, with a "✅ Model Answer" label.

### 5.7 No keyboard shortcut hints
**Fix:** Below the input, add a small hint line: `Enter to send · Shift+Enter for new line`.

### 5.8 Session mode toggle (Socratic / Exam prep) has no tooltip
**Fix:** Add `title` attributes or a `?` icon that explains what each mode does when hovered.

---

## 6. CONTENT TAB

### 6.1 Concept extraction is too coarse
**Problem:** A 991-page book produces only 10 concepts. Each concept has only a one-line description. There is no sub-concept hierarchy.  
**Fix:**  
- After chunking the PDF (see §1.1), run a concept-extraction prompt over all chunks:  
  ```
  From this passage, extract all distinct technical concepts.
  For each concept output: { name, definition, parentConcept (if any), pageRef }
  ```
- Cluster similar concepts and build a hierarchy (e.g. "Fine-tuning > PEFT > LoRA").
- Display as a collapsible tree in the Content tab, not a flat grid.

### 6.2 "Run ingest" button gives no progress feedback
**Problem:** After clicking "Run ingest," the button state doesn't change. The user has no idea if ingestion is running, stuck, or complete.  
**Fix:**  
- On click: disable button, change text to "Ingesting…", show a progress bar or spinner.
- On complete: flash "✓ Ingested — N chunks, M concepts found."
- On error: show red alert with the error message.

### 6.3 Document shows "0 chunks · pdf" after upload but before ingest
**Fix:**  
- Change label to "Ready to ingest" before ingest runs.
- After ingest completes, update to "N chunks · pdf."

### 6.4 No confirmation before deleting a document
**Problem:** The trash icon next to a document likely deletes it immediately.  
**Fix:** Show a confirmation modal: "Delete this document? All associated concepts and sessions will be unlinked."

---

## 7. SPACED REPETITION SYSTEM

### 7.1 Mastery score formula is opaque
**Problem:** Mastery shows as `0.18` and `0.20` with no explanation of what those numbers mean.  
**Fix:**  
- Show mastery as a percentage with a label: "18% — Needs practice."
- Define thresholds clearly in the UI: 0–30% = Needs practice, 31–60% = Developing, 61–85% = Proficient, 86–100% = Mastered.
- Color-code accordingly.

### 7.2 Review interval is hard-coded to 6 days for all concepts
**Problem:** The session report always says "Review in 6 days." A concept at 20% mastery should be reviewed sooner than one at 80%.  
**Fix:**  
- Implement SM-2 or a simple interval formula:  
  `nextInterval = max(1, currentInterval × easeFactor)`  
  where `easeFactor` is reduced on failure and increased on success.
- Map mastery score + session performance to the interval calculation.

---

## 8. ERRORS & RELIABILITY

### 8.1 No error boundary in the frontend
**Fix:** Wrap major React component trees in `<ErrorBoundary>` components that show a friendly "Something went wrong — reload" message instead of a blank screen.

### 8.2 API errors are swallowed silently
**Fix:** Every `fetch` / API call should have a `.catch` that at minimum logs to console **and** sets a visible error state in the UI (red toast / alert bar).

### 8.3 No retry logic for LLM calls
**Fix:** Wrap LLM API calls in an exponential-backoff retry (max 3 attempts) for transient errors (429, 503).

### 8.4 Session data is not persisted if the user closes the tab mid-session
**Fix:** Save session state to `localStorage` (or server) after every turn. On load, check for an unfinished session and offer to resume it.

---

## 9. ACCESSIBILITY & POLISH

### 9.1 No page titles or `aria-label` on interactive elements
**Fix:** Add `aria-label` to all icon buttons (send, delete, mode toggle). Set `<title>` per page/tab.

### 9.2 Color-only status encoding
**Problem:** Turn status (Got it / Stuck / Getting there) is communicated only through color, which fails for colorblind users.  
**Fix:** Always pair color with a text label or icon (✓ / ✗ / ~).

### 9.3 No dark mode support despite "Dark" toggle in nav
**Problem:** The Dark toggle exists in the nav (visible in screenshots) but apparently does nothing, or is broken.  
**Fix:** Implement a `data-theme="dark"` toggle on `<html>` and define CSS variables for both themes. Persist preference to `localStorage`.

### 9.4 Mobile layout is untested
**Fix:** Add responsive breakpoints. At minimum, ensure:
- Chat bubbles don't overflow on screens < 400px wide.
- Dashboard metric cards stack vertically on mobile.
- Report turns stack vertically.

---

## 10. QUICK WINS (Do These First)

| # | Issue | Effort | Impact |
|---|-------|--------|--------|
| A | Fix word-sticking in chat (space stripping bug) | Low | High |
| B | Add typing indicator (3 dots) | Low | High |
| C | Replace user bubble gradient with solid color | Low | Medium |
| D | Show concept names instead of UUIDs on dashboard | Low | High |
| E | Inline all CSS in report HTML | Low | High |
| F | Fix diagrams not rendering (add error logging first) | Medium | High |
| G | Add correct answer to each report turn | Medium | High |
| H | Disable Send button while awaiting response | Low | Medium |
| I | Add per-turn diagrams via background agent | High | High |
| J | Fix spaced-repetition review date query | Medium | High |

---

## 11. SUGGESTED ARCHITECTURE ADDITIONS

```
┌─────────────────────────────────────────────────────┐
│                  On User Answer                     │
│                                                     │
│  ┌──────────┐    ┌──────────────┐    ┌──────────┐  │
│  │ Grader   │    │ Diagram Gen  │    │  SR      │  │
│  │ Agent    │    │  Agent       │    │ Updater  │  │
│  │          │    │ (background) │    │          │  │
│  └──────────┘    └──────────────┘    └──────────┘  │
│       │                 │                  │        │
│       ▼                 ▼                  ▼        │
│  grade + label    SVG/Mermaid         mastery score │
│  stored in turn   stored in turn      updated in DB │
└─────────────────────────────────────────────────────┘
```

- **Grader Agent**: runs after every student turn. Returns `{ status, feedback, correctAnswer }`.
- **Diagram Agent**: runs in parallel (non-blocking). Returns `{ diagramType, diagramCode }`.
- **SR Updater**: after session end, recalculates mastery and writes `nextReviewDate`.
- All three write to the same turn record in the DB. The report reads from that enriched record.

---

*File generated: 2026-04-13. For use with Cursor AI — each numbered item is independently actionable.*
