from prometheus_client import Counter, Gauge, Histogram

TURN_LATENCY = Histogram(
    "tutor_turn_latency_seconds",
    "End-to-end latency per dialogue turn",
    buckets=[0.5, 1.0, 1.5, 2.0, 3.0, 5.0],
)

CLASSIFIER_STATE = Counter(
    "tutor_classifier_state_total",
    "Count of each understanding state",
    ["state"],
)

GUARDRAIL_TRIGGERS = Counter(
    "tutor_guardrail_triggers_total",
    "Times the anti-answer guard rejected a question",
)

REPETITION_RETRIES = Counter(
    "tutor_question_repetition_retries_total",
    "Regenerations triggered because the new question was too similar to a prior question",
)

ESCAPE_HATCH_ACTIVATIONS = Counter(
    "tutor_escape_hatch_total",
    "Stuck-streak override activations",
    ["concept_id"],
)

TOKENS_PER_TURN = Histogram(
    "tutor_tokens_per_turn",
    "Total tokens across all LLM calls per turn",
    buckets=[100, 500, 1000, 2000, 4000, 8000],
)

SESSION_DURATION_SECONDS = Histogram(
    "tutor_session_duration_seconds",
    "Wall-clock duration from session start to end",
    buckets=[30, 60, 120, 300, 600, 1800, 3600],
)

QUESTIONS_PER_SESSION = Histogram(
    "tutor_questions_per_session",
    "Number of tutor turns (student answers) recorded when session ends",
    buckets=[0, 1, 2, 3, 5, 8, 13, 21],
)

EXAM_SESSION_SCORE_PERCENT = Histogram(
    "tutor_exam_session_score_percent",
    "Final exam_prep score as percent of possible points (only observed when session ends in exam mode)",
    buckets=[0, 10, 20, 40, 60, 75, 90, 100],
)

MASTERY_SCORE = Gauge(
    "tutor_mastery_score",
    "Current mastery score per concept",
    ["concept_id"],
)
