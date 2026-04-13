from Utils.tutor_output_sanitize import sanitize_tutor_output

REAL_WORLD = '''MODE_LINE: probe_gap
TARGET_CONCEPT: Calculus
STUDENT_STATE: partial
GAP: null
SESSION_MODE: socratic
PRIOR_QUESTIONS: (none)
CONVERSATION: (Session start)
SOURCE_MATERIAL: (no retrieved chunks)

The user is starting a session on Calculus, and the state is 'partial'. Since there is no specific gap, I need to start by probing the foundational understanding of Calculus. I should ask a question that sets the stage for what Calculus is or what it involves.<channel|>What do you currently understand about the fundamental idea behind Calculus?
'''


def test_real_world_sample_yields_only_question():
    out = sanitize_tutor_output(REAL_WORLD)
    assert out == "What do you currently understand about the fundamental idea behind Calculus?"


def test_clean_text_unchanged():
    q = "How does the derivative relate to the slope of a tangent line?"
    assert sanitize_tutor_output(q) == q


def test_metadata_lines_only_no_delimiter():
    raw = """MODE_LINE: probe_gap
TARGET_CONCEPT: Calculus
STUDENT_STATE: partial

What is one idea you associate with limits?
"""
    out = sanitize_tutor_output(raw)
    assert "MODE_LINE" not in out
    assert "TARGET_CONCEPT" not in out
    assert "What is one idea you associate with limits?" in out


def test_empty_and_none():
    assert sanitize_tutor_output("") == ""
    assert sanitize_tutor_output(None) == ""


def test_alternate_channel_delimiter():
    raw = "Planning text here.<|channel|>What is X?"
    assert sanitize_tutor_output(raw) == "What is X?"
