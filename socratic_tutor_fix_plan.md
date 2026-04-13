# Socratic Tutor — Bug Investigation & Fix Plan

> This plan is for an AI agent to implement. Read every section before touching any file.
> All file paths are relative to the repo root.

---

## Diagnosed Bugs

Two distinct failure modes are occurring, each with a different root cause.

### Bug A — "Tell me more" / Generic Question Loop

**Symptom:** Regardless of the student's answer, the tutor always responds with some variant of _"Can you tell me more about what you understand about X?"_ — a completely generic probe that ignores conversation history and the classifier output.

**Root cause (two sub-causes that compound each other):**

1. **Conversation memory is empty when the question generator runs.** `build_memory(state["messages"])` is likely receiving an empty or single-message list because `state["messages"]` is not accumulating across turns. In LangGraph, `Annotated[list, add_messages]` only appends correctly if the node's return value uses the `messages` key. If `probe_node` returns `{"messages": [AIMessage(content=question)]}` but the student's incoming message was already appended elsewhere (or not at all), the memory builder sees only the AI's last message and has no student context to work from.

2. **The `gap` field from the classifier is `None` or not forwarded.** The `SOCRATIC_SYSTEM` prompt template uses `{gap}` to target the exact missing piece. If the classifier returns `null` for gap on a `partial` state, the generator has no specific angle to probe and falls back to the LLM's generic "tell me more" behaviour.

### Bug B — Full Conversation Reset / Restart

**Symptom:** After several turns, the tutor asks _"What comes to mind when you think about X?"_ again — the exact opening question, as if the session was restarted from scratch. The second example shows the entire exchange literally replaying.

**Root cause (two sub-causes):**

1. **`session_id` / `thread_id` not propagated correctly to the LangGraph checkpointer.** With `PostgresSaver`, every `graph.invoke()` / `graph.astream()` call must receive `config={"configurable": {"thread_id": session_id}}` using the **same** `session_id` that was used on turn 1. If the `SessionController` generates a new `thread_id` on each HTTP request (e.g. using `uuid4()` at invocation time instead of reading the persisted `session_id`), LangGraph creates a new graph thread every turn — no history, back to the opening question.

2. **`probe_turns` counter is not being saved between requests.** If the `ConceptState.probe_turns` increment in `probe_node` is lost (either because `current_concept` is overwritten rather than updated via `model_copy(update=...)`, or because the checkpointer commit fails silently), `route_probe` always sees `probe_turns == 0` and routes to a fresh PROBE start.

---

## Files to Investigate and Modify

Read every file listed below before writing any changes. Understand the full call chain first.

```
SRC/Controllers/SessionController.py     # primary suspect for Bug B
SRC/Engine/nodes.py                      # primary suspect for Bug A
SRC/Engine/edges.py                      # secondary suspect for Bug B
SRC/Engine/state.py                      # verify TypedDict definitions
SRC/Engine/graph.py                      # verify graph compilation + checkpointer wiring
SRC/Engine/agents/QuestionGenerator.py  # verify prompt template interpolation
SRC/Engine/agents/Classifier.py         # verify structured output + gap field
SRC/Utils/ContextManager.py             # verify build_memory return value
SRC/Routes/Session.py                   # verify session_id extraction from request
```

---

## Fix 1 — Thread ID Propagation (Bug B, primary fix)

**File: `SRC/Controllers/SessionController.py`**

Find where `graph.invoke()` or `graph.astream()` is called. Verify that the `config` dict is constructed using the session's persisted `id` from the database, not a freshly generated UUID.

**Wrong pattern (generates a new thread every call):**
```python
config = {"configurable": {"thread_id": str(uuid4())}}
result = await graph.astream(input_state, config=config)
```

**Correct pattern:**
```python
# session.id must be the UUID that was persisted to PostgreSQL at session start
config = {"configurable": {"thread_id": str(session.id)}}
result = await graph.astream(input_state, config=config)
```

Also verify the session `id` is being read from the database (or from the URL path parameter) and is NOT re-derived from any request body field that the frontend might be generating freshly. The `session_id` used in `POST /api/v1/session/start` to create the DB row must be the exact same UUID used as `thread_id` in every subsequent `POST /api/v1/session/{id}/turn` call.

**File: `SRC/Routes/Session.py`**

Confirm the path parameter `{id}` in `POST /api/v1/session/{id}/turn` is extracted and passed down to `SessionController`. If it is being shadowed by a body field or a middleware is regenerating it, fix that.

---

## Fix 2 — Message Accumulation (Bug A, primary fix)

**File: `SRC/Engine/nodes.py` → `probe_node`**

The LangGraph `add_messages` reducer appends messages — but only if the student's incoming message is itself added to `state["messages"]` before `probe_node` runs. Trace where the human turn message is added to graph state. It must happen via the `messages` key, not a separate field like `student_input`.

**Checklist:**
- When the `/turn` endpoint receives a student answer, the `SessionController` should add a `HumanMessage(content=student_answer)` to the graph input. Verify this.
- `probe_node` must return `{"messages": [AIMessage(content=question)]}` — the list must contain exactly the new AI message; do not return the full history here (the reducer handles accumulation).
- After these two points are correct, `state["messages"]` will contain the full chronological conversation and `build_memory(state["messages"])` will work.

**Concrete check in `probe_node`:**
```python
# CORRECT — add only the new message, let add_messages accumulate
return {
    "messages": [AIMessage(content=question)],
    "current_concept": concept.model_copy(update={...})
}

# WRONG — overwrites the entire messages list
return {
    "messages": [HumanMessage(content=student_input), AIMessage(content=question)],
    ...
}
```

**File: `SRC/Utils/ContextManager.py` → `build_memory`**

Add a defensive guard so that if the messages list is shorter than expected, it still returns a meaningful string rather than an empty one:

```python
def build_memory(self, messages: list) -> str:
    if not messages:
        return ""
    recent = messages[-self.MAX_RAW_TURNS * 2:]  # *2 because human + AI pairs
    pairs = []
    for i in range(0, len(recent) - 1, 2):
        human = recent[i]
        ai = recent[i + 1] if i + 1 < len(recent) else None
        student_text = human.content if hasattr(human, "content") else str(human)
        tutor_text = ai.content if ai and hasattr(ai, "content") else ""
        pairs.append(f"Student: {student_text}\nTutor: {tutor_text}")
    return "\n\n".join(pairs)
```

---

## Fix 3 — Gap Field Propagation (Bug A, secondary fix)

**File: `SRC/Engine/agents/Classifier.py`**

Verify the structured output schema for the classifier enforces that `gap` is always a non-null string when state is `partial` or `wrong`. If the LLM returns `"gap": null` for a `partial` classification, the question generator has nothing specific to probe.

Update the classifier prompt to make this explicit:

```
Rules:
- "correct": student demonstrates clear understanding of the target concept
- "partial": student shows some understanding but misses a key part
  → gap MUST be a specific one-sentence description of what is missing
- "wrong": student's answer is factually incorrect
  → gap MUST describe the specific misconception
- "stuck": student says they don't know, asks for help, or gives a non-answer
  → gap should be null

IMPORTANT: For "partial" and "wrong" states, a null or empty gap is invalid.
Describe the gap in concrete terms tied to the concept.
```

**File: `SRC/Engine/nodes.py` → `probe_node`**

Add a fallback in case gap is still null for `partial`/`wrong`:

```python
gap = classifier_result.gap
if classifier_result.state in ("partial", "wrong") and not gap:
    gap = f"the student has not fully explained the core mechanism of {concept.name}"
```

---

## Fix 4 — Prompt Template Interpolation (Bug A, tertiary fix)

**File: `SRC/Engine/agents/QuestionGenerator.py`**

Verify that all four template variables — `{concept}`, `{state}`, `{gap}`, `{memory}` — are being substituted before the LLM call. If any variable is missing from the `format()` call (or if a different interpolation method like f-strings is used inconsistently), the LLM receives a literal `{memory}` string which it may silently ignore.

Check for this exact pattern:

```python
# Find the prompt formatting call. It must look like this:
prompt = SOCRATIC_SYSTEM.format(
    concept=concept.name,
    state=classifier_result.state,
    gap=gap or "none identified",
    memory=memory or "No prior turns."
)
```

If `memory` or `gap` evaluates to an empty string or `None`, the LLM will see an empty context slot and generate a generic question. Provide explicit fallback strings as shown above.

---

## Fix 5 — `current_concept` State Persistence (Bug B, secondary fix)

**File: `SRC/Engine/nodes.py` → `probe_node`**

The `probe_turns` increment must use `model_copy(update=...)` correctly and the result must be returned under the `current_concept` key. Confirm this:

```python
updated_concept = concept.model_copy(update={
    "probe_turns": concept.probe_turns + 1,
    "classifier_states": [*concept.classifier_states, classifier_result.state],
    "stuck_streak": (
        concept.stuck_streak + 1 if classifier_result.state == "stuck" else 0
    )
})
return {
    "messages": [AIMessage(content=question)],
    "current_concept": updated_concept   # ← must be the updated copy
}
```

If `current_concept` is a `ConceptState` Pydantic model inside a `TypedDict`, LangGraph will replace the value wholesale — this is correct. If `concept` was being mutated directly (`.probe_turns += 1`) and then the original reference returned, the checkpointer may or may not capture the mutation depending on serialisation timing.

---

## Fix 6 — Graph Input Shape on `/turn` (Bug B + Bug A combined)

**File: `SRC/Controllers/SessionController.py`**

When calling `graph.astream()` for a turn (not session start), the input to the graph must only contain the new delta — specifically the new human message. It must NOT pass a fresh `SessionState` with reset values. With `PostgresSaver`, LangGraph merges the input with the checkpointed state; if you pass a full state dict, it may overwrite checkpointed values.

**Wrong pattern (overwrites checkpointed state):**
```python
input_state = {
    "session_id": session_id,
    "user_id": user_id,
    "phase": "PROBE",                # ← this will overwrite the persisted phase
    "current_concept": concept,      # ← this will overwrite probe_turns counter
    "messages": [HumanMessage(content=student_answer)],
    ...
}
await graph.astream(input_state, config=config)
```

**Correct pattern (only send the new human message as delta):**
```python
input_delta = {
    "messages": [HumanMessage(content=student_answer)]
}
await graph.astream(input_delta, config=config)
```

The checkpointer restores everything else (phase, current_concept, concept_queue, etc.) from the persisted state. Sending a partial input is intentional and correct.

---

## Fix 7 — Opening Question vs. Probe Question Distinction

**File: `SRC/Engine/nodes.py`**

The "What comes to mind when you think about X?" question should only fire on `probe_turns == 0` (i.e. the very first turn of a concept). All subsequent turns should use the SOCRATIC_SYSTEM prompt driven by the classifier. If there is a separate `opening_question_node` or if `probe_node` uses a different branch for turn 0, ensure it is only reachable when `probe_turns == 0`.

If there is no explicit turn-0 branch and the opening question is always being generated, this is further evidence that `probe_turns` is always 0 (confirming Fix 5 is needed) or that the graph is re-entering the concept from the start (confirming Fix 1 is needed).

**Explicit guard to add:**
```python
async def probe_node(state: SessionState, config: RunnableConfig) -> dict:
    concept = state["current_concept"]

    # Turn 0: generate opening question directly, skip classifier
    if concept.probe_turns == 0:
        opening = f"What comes to mind when you think about {concept.name}?"
        return {
            "messages": [AIMessage(content=opening)],
            "current_concept": concept.model_copy(update={"probe_turns": 1})
        }

    # Turn 1+: classify then generate
    classifier_result = await classify_answer(...)
    ...
```

This means the opening question node is idempotent — if probe_turns is correctly persisted at 1 after the first turn, it will never fire again for the same concept.

---

## Fix 8 — Stuck Streak → Escape Hatch Not Triggering

**Symptom from Bug A second example:** The tutor asks "What is one concrete example from the material that relates to this concept?" repeatedly even after the student has answered. This is the scaffold question for `stuck` state. The escape hatch (`stuck_streak >= 3` → `micro_explain`) is not triggering.

**Root cause:** `stuck_streak` is not incrementing across turns (same state persistence issue as `probe_turns`). Once Fix 5 is applied, this should self-correct.

**Additionally, in `SRC/Engine/agents/QuestionGenerator.py`:** The scaffold question for `stuck` state must vary based on conversation history. If `memory` is empty (Bug A), the generator has no way to know it already asked for "a concrete example" and asks again. Once Fix 2 is applied (memory working), it will generate varied scaffold questions.

**Extra safeguard — add question deduplication:**
```python
# In probe_node, after generating the question:
last_ai_messages = [
    m.content for m in state["messages"]
    if isinstance(m, AIMessage)
][-3:]  # last 3 tutor questions

# If the new question is too similar to a recent one, regenerate once
if any(similarity(question, prev) > 0.85 for prev in last_ai_messages):
    question = await generate_socratic_question(
        classifier_result=classifier_result,
        concept=concept,
        memory=memory,
        llm=llm_gen,
        variation_hint="Ask from a completely different angle than previous questions."
    )
```

A simple similarity check (e.g. `difflib.SequenceMatcher`) is sufficient here.

---

## Fix 9 — Frontend Session ID Handling

**File: `frontend/src/api/` (whichever file handles session turn calls)**

Verify that the frontend:
1. Stores the `session_id` returned by `POST /api/v1/session/start` in component state or Zustand store.
2. Sends the correct `session_id` in the URL path on every `POST /api/v1/session/{id}/turn` call.
3. Does NOT re-create the session (call `/start` again) on page refresh or hot-reload without checking if a session is already active.

If the frontend calls `/start` again on hot-reload (common in Vite dev mode with `useEffect` running twice in StrictMode), a new session is created server-side and the old conversation is lost. Fix:

```typescript
// In your session store / hook, guard the start call:
useEffect(() => {
  if (!sessionId) {  // only start if no session is active
    startSession(conceptId).then(({ session_id }) => {
      setSessionId(session_id);
    });
  }
}, [conceptId]);
```

---

## Verification Checklist

After applying all fixes, verify the following test scenarios manually:

| Scenario | Expected behaviour | Passes? |
|---|---|---|
| Start session, send one answer | Tutor asks a contextually relevant follow-up, not the same opening question | |
| Send 3 `"I don't know"` answers in a row | `stuck_streak` reaches 3, tutor provides a brief micro-explanation then asks a simpler question | |
| Restart backend while session is in progress, resume from frontend | Same session_id → LangGraph restores state from PostgreSQL, conversation continues | |
| Send a correct, complete answer | Classifier returns `correct` > 0.85 → phase transitions to REVEAL (Stage 2) or session ends (Stage 1) | |
| Send a partial answer | Classifier returns `partial` with a specific `gap` → tutor asks a question targeting that exact gap | |
| Complete 5 probe turns without mastery signal | `probe_turns >= max_probe_turns` → transitions to REVEAL | |

---

## Order of Implementation

Apply fixes in this order to minimise debugging confusion:

1. **Fix 1** (thread_id propagation) — eliminates the restart bug entirely, makes all other bugs reproducible in isolation
2. **Fix 6** (graph input shape on /turn) — ensures state is not overwritten on each turn
3. **Fix 5** (`current_concept` state persistence) — ensures probe_turns and stuck_streak accumulate
4. **Fix 2** (message accumulation) — enables memory to work
5. **Fix 7** (opening question guard) — prevents opening question from ever re-appearing
6. **Fix 3** (gap field propagation) — makes partial-state questions specific
7. **Fix 4** (prompt template interpolation) — ensures all template variables are filled
8. **Fix 8** (question deduplication) — prevents identical scaffold questions
9. **Fix 9** (frontend session ID) — prevents dev-mode double-invocation

Do not batch all fixes and test together. Apply Fix 1 + Fix 6, verify the session no longer restarts, then proceed.

---

## Root Cause Summary

Both bugs share one underlying pattern: **LangGraph graph state is not being preserved between HTTP requests.** Everything else — the generic questions, the stuck loops, the repeating conversation — is a downstream symptom of the engine operating on blank state on each turn. Fix the thread_id propagation and graph input shape first, and most of the dialogue quality problems will resolve themselves.
