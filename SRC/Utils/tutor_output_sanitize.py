"""Strip echoed prompt structure and model delimiters from tutor completions."""

from __future__ import annotations

import re

# Gemini / internal delimiters sometimes appear before the visible answer.
_CHANNEL_SPLIT = re.compile(r"<(?:channel\||\|channel\|)>", re.IGNORECASE)

# Lines that echo SOCRATIC_USER_TEMPLATE / MODE_LINE (prefix match after strip).
_METADATA_PREFIXES: tuple[str, ...] = (
    "mode_line:",
    "target_concept:",
    "student_state:",
    "gap:",
    "session_mode:",
    "prior_questions:",
    "conversation:",
    "source_material:",
)

# Single-line XML-style tags sometimes echoed by models.
_XML_LINE = re.compile(
    r"^\s*<(?P<tag>[A-Z_]+)>(?P<body>[^<]*)</(?P=tag)>\s*$",
    re.IGNORECASE,
)


def _strip_metadata_lines(text: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    for line in lines:
        low = line.strip().lower()
        if any(low.startswith(p) for p in _METADATA_PREFIXES):
            continue
        if _XML_LINE.match(line):
            continue
        kept.append(line)
    return "\n".join(kept)


def _strip_leading_cot_paragraph(text: str) -> str:
    """Remove a first paragraph that looks like model planning, not the tutor line."""
    t = text.strip()
    if not t:
        return t
    low = t.lower()
    if not (
        low.startswith("the user ")
        or low.startswith("i need to ")
        or low.startswith("since ")
    ):
        return t
    if "\n\n" in t:
        return t.split("\n\n", 1)[1].strip()
    return t


def sanitize_tutor_output(text: str | None) -> str:
    """
    Return user-visible tutor text: drop echoed CONTEXT fields, metadata lines,
    and take content after channel delimiters when present.
    """
    if text is None:
        return ""
    raw = text.strip()
    if not raw:
        return ""

    work = raw
    # Prefer content after the last delimiter (prefix + delimiter + question).
    parts = _CHANNEL_SPLIT.split(work)
    if len(parts) > 1:
        work = parts[-1].strip()

    work = _strip_metadata_lines(work)
    work = _strip_leading_cot_paragraph(work)
    work = re.sub(r"\n{3,}", "\n\n", work).strip()

    if not work:
        return raw
    return work
